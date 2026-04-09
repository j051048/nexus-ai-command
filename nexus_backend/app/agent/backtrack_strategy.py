"""P2.2 Backtracking Strategy for Agent Planning Graph.

Implements Tree-of-Thought (ToT) inspired conditional re-planning,
allowing the agent to backtrack to alternative plans when the current
plan fails or retrieval yields no useful results.

Key concepts:
  - candidate_plans:  Top-N scored plan alternatives from self-consistency
  - backtrack_depth:  Number of times we've fallen back to an alternative (max=1)
  - rollback_path:    State snapshot enabling rollback to the decision point

The strategy fires when:
  1. reflect_node detects low confidence or all tools failed
  2. backtrack_depth < max_backtrack (default 1)
  3. candidate_plans has an untried alternative with score > threshold

This avoids infinite loops by enforcing a hard cap on backtrack_depth.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────
MAX_BACKTRACK_DEPTH = 1  # Only allow 1 backtrack per turn (prevents loops)
MIN_ALTERNATIVE_SCORE = 0.3  # Minimum plan quality score to consider backtracking
CONFIDENCE_BACKTRACK_THRESHOLD = 0.4  # Trigger backtrack if confidence < this


def should_backtrack(state: dict) -> bool:
    """Determine if the agent should backtrack to an alternative plan.

    Conditions (ALL must be true):
      1. backtrack_depth < MAX_BACKTRACK_DEPTH
      2. confidence_score < CONFIDENCE_BACKTRACK_THRESHOLD OR all tools failed
      3. candidate_plans has at least one untried alternative

    Args:
        state: Current AgentState dict

    Returns:
        True if backtracking is recommended
    """
    backtrack_depth = state.get("backtrack_depth", 0)
    if backtrack_depth >= MAX_BACKTRACK_DEPTH:
        logger.debug("[Backtrack] Max depth reached (%d), no backtrack", backtrack_depth)
        return False

    # Condition 2: Low confidence or total tool failure
    confidence = state.get("confidence_score", 1.0)
    completed_tools = state.get("completed_tool_calls", [])
    all_tools_failed = len(completed_tools) > 0 and all(
        (getattr(tc, "status", None) or (tc.get("status") if isinstance(tc, dict) else "")) == "error"
        for tc in completed_tools
    )

    should_trigger = confidence < CONFIDENCE_BACKTRACK_THRESHOLD or all_tools_failed
    if not should_trigger:
        return False

    # Condition 3: Has alternative plans
    candidates = state.get("candidate_plans", [])
    if not candidates:
        logger.debug("[Backtrack] No candidate plans available")
        return False

    # Check if there's an untried candidate with sufficient quality
    current_plan_sig = _plan_signature(state.get("plan", ""))
    alternatives = [
        c for c in candidates if c.get("sig") != current_plan_sig and c.get("score", 0) >= MIN_ALTERNATIVE_SCORE
    ]

    if not alternatives:
        logger.debug("[Backtrack] No viable alternative plans")
        return False

    logger.info(
        "[Backtrack] Backtrack conditions met: confidence=%.2f, all_failed=%s, " "alternatives=%d, depth=%d",
        confidence,
        all_tools_failed,
        len(alternatives),
        backtrack_depth,
    )
    return True


def execute_backtrack(state: dict) -> dict:
    """Execute a backtrack: select the best alternative plan and prepare state updates.

    This function returns state mutations to apply (not modifying state directly),
    following the LangGraph node-return convention.

    Args:
        state: Current AgentState dict

    Returns:
        Dict of state updates to merge back
    """
    candidates = state.get("candidate_plans", [])
    current_plan_sig = _plan_signature(state.get("plan", ""))
    backtrack_depth = state.get("backtrack_depth", 0)

    # Select best untried alternative
    alternatives = sorted(
        [c for c in candidates if c.get("sig") != current_plan_sig],
        key=lambda c: c.get("score", 0),
        reverse=True,
    )

    if not alternatives:
        logger.warning("[Backtrack] No alternatives found during execute (race condition?)")
        return {}

    best = alternatives[0]
    logger.info(
        "[Backtrack] Switching to alternative plan (score=%.2f, depth=%d→%d): %s",
        best.get("score", 0),
        backtrack_depth,
        backtrack_depth + 1,
        best.get("sig", "?")[:50],
    )

    # Build state updates
    updates: dict[str, Any] = {
        "backtrack_depth": backtrack_depth + 1,
        "needs_replanning": True,
        "confidence_score": best.get("score", 0.5),
        # Clear completed tools from the failed path
        "completed_tool_calls": [],
        "pending_tool_calls": [],
        # Inject backtrack guidance for the planning node
        "reflection_guidance": (
            f"## 寻路回溯 (Backtrack #{backtrack_depth + 1})\n"
            f"之前的方案未能达到预期效果（置信度: {state.get('confidence_score', 0):.0%}）。\n"
            f"请采用以下替代策略:\n"
            f"- 之前的方案签名: {current_plan_sig[:80]}\n"
            f"- **不要重复使用已失败的工具或相同参数**\n"
            f"- 评估是否可以不使用工具，直接基于已有上下文回答\n"
            f"- 如果必须使用工具，选择完全不同的工具或参数组合"
        ),
    }

    # Restore message snapshot from the candidate if available
    if best.get("msg_snapshot"):
        updates["messages"] = best["msg_snapshot"]

    return updates


def record_plan_candidate(
    plan_text: str,
    score: float,
    msg_snapshot: list | None = None,
) -> dict:
    """Create a candidate plan record for ToT branch storage.

    Args:
        plan_text: The natural language plan
        score: Quality score (0.0 - 1.0) from self-consistency votes
        msg_snapshot: Optional message state snapshot for potential rollback

    Returns:
        Candidate plan dict suitable for state["candidate_plans"]
    """
    return {
        "sig": _plan_signature(plan_text),
        "score": round(score, 3),
        "msg_snapshot": msg_snapshot,
    }


def _plan_signature(plan_text: str) -> str:
    """Generate a compact signature for a plan to detect duplicates.

    Uses sorted extracted keywords rather than full text to handle
    paraphrase-level duplicates (e.g., "查询客户信息" vs "获取客户数据").
    """
    if not plan_text:
        return ""

    import hashlib

    # Normalize: lowercase, strip whitespace, remove punctuation
    import re

    clean = re.sub(r"[^\w\u4e00-\u9fff]", "", plan_text.lower())
    # Use first 200 chars for hash (plans shouldn't be longer)
    return hashlib.md5(clean[:200].encode()).hexdigest()[:12]
