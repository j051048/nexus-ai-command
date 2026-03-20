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

# Sliding window size for tool call history analysis
LOOP_WINDOW_SIZE = 30
# Thresholds for different detection strategies
GENERIC_REPEAT_THRESHOLD = 3       # Same tool+args N times → force reflect
POLL_NO_PROGRESS_THRESHOLD = 5     # Polling tools with no progress → block
GLOBAL_CIRCUIT_BREAKER = 15        # Absolute safety net: any single tool N times → block

# Tools known to cause polling loops (status checks, process waits)
POLL_TOOLS: set[str] = {
    "get_company_stats", "query_leave_status", "query_expense_status",
    "query_attendance", "get_pending_approvals",
}


# ─── Public API ───────────────────────────────────────────────────────────────


def tool_call_fingerprint(tool_calls: list) -> str:
    """Generate a hash fingerprint for a set of tool calls (name + args)."""
    if not tool_calls:
        return ""
    parts = []
    for tc in sorted(tool_calls, key=lambda t: t.tool_name):
        args_str = json.dumps(tc.tool_args, sort_keys=True, ensure_ascii=False) if tc.tool_args else ""
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
                logger.warning(f"[LoopDetect] Poll no-progress: {poll_tool} called {count} times")
                return True

    # --- Detector 4: Global Circuit Breaker ---
    if completed:
        recent_completed = completed[-LOOP_WINDOW_SIZE:]
        tool_counts = Counter(tc.tool_name for tc in recent_completed)
        for tool_name, count in tool_counts.items():
            if count >= GLOBAL_CIRCUIT_BREAKER:
                logger.warning(f"[LoopDetect] Circuit breaker: {tool_name} called {count} times")
                return True

    return False
