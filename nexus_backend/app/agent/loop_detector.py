"""
Loop Detection — Multi-strategy detector for agent tool-call loops.

Extracted from graph.py for modularity and independent testability.
Inspired by OpenClaw tool-loop-detection.ts.

4 detection strategies:
  1. Generic Repeat: same tool+args fingerprint N times consecutively
  2. Ping-Pong: A-B-A-B alternating pattern
  3. Known Poll No-Progress: polling tools called repeatedly
  4. Global Circuit Breaker: any single tool exceeds absolute limit
"""

import hashlib
import json
import logging
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent.state import AgentState

logger = logging.getLogger(__name__)

# ─── Configuration Constants ─────────────────────────────────────────────────
from app.core.config import settings

LOOP_WINDOW_SIZE = settings.LOOP_WINDOW_SIZE
GENERIC_REPEAT_THRESHOLD = settings.LOOP_GENERIC_REPEAT_THRESHOLD
POLL_NO_PROGRESS_THRESHOLD = settings.LOOP_POLL_NO_PROGRESS_THRESHOLD
GLOBAL_CIRCUIT_BREAKER = settings.LOOP_GLOBAL_CIRCUIT_BREAKER

# Tools known to cause polling loops (status checks, process waits)
POLL_TOOLS: set[str] = {
    "get_company_stats",
    "query_leave_status",
    "query_expense_status",
    "query_attendance",
    "get_pending_approvals",
}


# ─── Public API ───────────────────────────────────────────────────────────────


def tool_call_fingerprint(tool_calls: list) -> str:
    """Generate a hash fingerprint for a set of tool calls (name + args)."""
    if not tool_calls:
        return ""
    parts = []
    for tc in sorted(tool_calls, key=lambda t: t.tool_name):
        args_str = (
            json.dumps(tc.tool_args, sort_keys=True, ensure_ascii=False)
            if tc.tool_args
            else ""
        )
        parts.append(f"{tc.tool_name}:{args_str}")
    combined = "|".join(parts)
    return hashlib.md5(combined.encode()).hexdigest()


def detect_loop(state: "AgentState") -> bool:
    """
    Multi-strategy loop detection (4 detectors).

    Returns True if a loop pattern is detected in the tool call history.
    """
    from app.agent.state import get_completed_tools

    history = state.get("_tool_call_history", [])
    if len(history) < 2:
        return False

    window = history[-LOOP_WINDOW_SIZE:]

    # --- Detector 1: Generic Repeat (same fingerprint N consecutive times) ---
    if len(window) >= GENERIC_REPEAT_THRESHOLD:
        recent = window[-GENERIC_REPEAT_THRESHOLD:]
        if len(set(recent)) == 1 and recent[0] != "":
            logger.warning(f"[LoopDetect] Generic repeat detected: {recent[0][:16]}...")
            return True

    # --- Detector 2: Ping-Pong (A-B-A-B alternating) ---
    if len(window) >= 4:
        last4 = window[-4:]
        if last4[0] == last4[2] and last4[1] == last4[3] and last4[0] != last4[1]:
            logger.warning("[LoopDetect] Ping-pong pattern detected")
            return True

    # --- Detector 3: Known Poll No-Progress ---
    completed = get_completed_tools(state)
    if completed:
        recent_completed = completed[-LOOP_WINDOW_SIZE:]
        for poll_tool in POLL_TOOLS:
            count = sum(1 for tc in recent_completed if tc.tool_name == poll_tool)
            if count >= POLL_NO_PROGRESS_THRESHOLD:
                logger.warning(
                    f"[LoopDetect] Poll no-progress: {poll_tool} called {count} times"
                )
                return True

    # --- Detector 4: Global Circuit Breaker ---
    if completed:
        recent_completed = completed[-LOOP_WINDOW_SIZE:]
        tool_counts = Counter(tc.tool_name for tc in recent_completed)
        for tool_name, count in tool_counts.items():
            if count >= GLOBAL_CIRCUIT_BREAKER:
                logger.warning(
                    f"[LoopDetect] Circuit breaker: {tool_name} called {count} times"
                )
                return True

    return False


async def record_tool_call_redis(session_id: str, tool_name: str) -> bool:
    """P0-9: Redis-backed cross-worker circuit breaker.

    Records tool call count per session in Redis. Returns True if breaker tripped.
    TTL = 1 hour (sessions rarely last longer for a single invocation chain).
    """
    try:
        from app.services.cache_service import cache_service

        if not (cache_service._use_redis and cache_service._client):
            return False
        key = f"loop_detect:{session_id}:{tool_name}"
        count = await cache_service._client.incr(key)
        if count == 1:
            await cache_service._client.expire(key, 3600)
        if count >= GLOBAL_CIRCUIT_BREAKER:
            logger.warning(
                f"[LoopDetect] Redis circuit breaker: {tool_name} x{count} in session {session_id[:8]}"
            )
            return True
    except Exception as e:
        logger.debug(f"[LoopDetect] Redis record skipped: {e}")
    return False
