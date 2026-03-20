"""
Safety Guards — Irreversible tool detection, mutation fast-path, and SLO checks.

Extracted from graph.py for modularity.

Guards:
  G1: Irreversible tools (financial approvals, destructive ops) must always
      go through Critic review — never take a fast path.
  SLO: Dynamic time-budget checks per complexity level.
"""

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent.state import AgentState

from app.agent.state import QueryComplexity
from app.tools import get_tool

logger = logging.getLogger(__name__)

# ── SLO thresholds (seconds) per complexity level ──
SLO_THRESHOLDS: dict[QueryComplexity, float] = {
    QueryComplexity.SIMPLE: 5.0,
    QueryComplexity.MODERATE: 10.0,
    QueryComplexity.COMPLEX: 20.0,
    QueryComplexity.CRITICAL: 30.0,
}


def has_irreversible_tool(state_or_dict: dict) -> bool:
    """
    Check if any completed tool call used an irreversible (high-risk) tool.

    G1: Irreversible tools (financial approvals, destructive ops, etc.) must
    always go through Critic review — they should NEVER take a fast path.
    """
    completed = state_or_dict.get("completed_tool_calls", [])
    for tc in completed:
        tool = get_tool(getattr(tc, "tool_name", "") or (tc.get("tool_name", "") if isinstance(tc, dict) else ""))
        if tool and tool.is_irreversible:
            return True
    return False


def is_mutation_fast_path(state_or_dict: dict) -> bool:
    """
    Check if all completed tool calls are successful mutations that can
    safely skip reflect+critic.

    Returns False (no fast path) when:
    - No completed tools
    - Any tool failed
    - Any tool is irreversible (G1: high-risk tools must go through Critic)
    """
    completed = state_or_dict.get("completed_tool_calls", [])
    if not completed:
        return False
    # G1: irreversible tools MUST go through Critic — never fast-path
    if has_irreversible_tool(state_or_dict):
        logger.info(
            "[Graph] Irreversible tool detected, blocking mutation fast-path → forcing Critic review"
        )
        return False
    for tc in completed:
        if getattr(tc, "status", None) != "success":
            return False
        tool = get_tool(getattr(tc, "tool_name", ""))
        if not tool:
            return False
    return True


def check_slo_budget(state: "AgentState", budget_ratio: float = 1.0) -> bool:
    """
    Check if the agent has exceeded its SLO time budget.

    Args:
        state: Current agent state
        budget_ratio: Fraction of the SLO budget to check against (e.g. 0.8 for 80%)

    Returns:
        True if SLO budget is exceeded, False otherwise.
    """
    wall_start = state.get("wall_clock_start")
    complexity = state.get("complexity")
    if not wall_start or not complexity:
        return False
    elapsed = time.time() - wall_start
    threshold = SLO_THRESHOLDS.get(complexity, 20.0) * budget_ratio
    if elapsed > threshold:
        logger.info(
            f"[SLO] Budget exceeded: {elapsed:.1f}s > {threshold:.1f}s "
            f"(complexity={complexity}, ratio={budget_ratio})"
        )
        return True
    return False
