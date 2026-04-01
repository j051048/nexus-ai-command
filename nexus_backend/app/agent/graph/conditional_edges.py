"""
Conditional edge functions for LangGraph routing.

Extracted from graph.py to improve modularity.
Each function determines the next node based on current state.
"""

import asyncio
import logging
import time

from app.agent.loop_detector import detect_loop
from app.agent.safety_guards import SLO_THRESHOLDS, has_irreversible_tool, is_mutation_fast_path
from app.agent.state import AgentState, QueryComplexity, get_completed_tools, get_task_steps

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task] = set()


def after_plan(state: AgentState) -> str:
    """Route after planning node."""
    if state.get("error"):
        return "error"
    if state.get("requires_tools") and state.get("pending_tool_calls"):
        return "slot_verify"
    if state.get("complexity") == QueryComplexity.SIMPLE:
        return "respond"

    reflection_count = state.get("reflection_count", 0)
    if reflection_count >= 2:
        logger.info(f"[Graph] Reflection budget exhausted ({reflection_count}/2)")
        return "respond"

    if state.get("complexity") == QueryComplexity.MODERATE and not get_completed_tools(state):
        return "respond"

    if is_mutation_fast_path(state):
        logger.info("[Graph] Mutation fast-path: skipping reflect+critic")
        return "respond"

    return "reflect"


def after_slot_verify(state: AgentState) -> str:
    """Route after slot verification."""
    if state.get("error"):
        return "error"
    if state.get("slot_context"):
        return "respond"
    return "execute"


def after_execute(state: AgentState) -> str:
    """Route after tool execution."""
    if state.get("error"):
        return "error"

    if state.get("confirmation_pending"):
        logger.info("[Graph] Confirmation pending (HITL gate)")
        return "respond"

    config = state.get("config")
    max_iter = config.max_iterations if config else 5
    iteration = state.get("iteration", 0)

    completed = get_completed_tools(state)
    tool_summary = ", ".join(
        f"{tc.tool_name}={'ok' if tc.status == 'success' else tc.status}"
        for tc in completed[-5:]
    ) if completed else "none"

    logger.info(
        f"[Graph] after_execute: iter={iteration}/{max_iter} "
        f"tools=[{tool_summary}]"
    )

    if iteration >= max_iter:
        logger.warning(f"[Graph] Max iterations reached")
        state["circuit_break_reason"] = "max_iterations"
        return "reflect"

    if detect_loop(state):
        if not state.get("_loop_escape_attempted"):
            logger.warning("[Graph] Loop detected, attempting strategy reset")
            state["_loop_escape_attempted"] = True
            state["reflection_guidance"] = (
                "⚠️ 检测到工具调用循环。请尝试不同的方法。"
            )
            return "plan"

        logger.warning("[Graph] Loop persists, forcing circuit break")
        state["circuit_break_reason"] = "loop_detected"
        return "reflect"

    complexity = state.get("complexity")
    if completed and all(tc.status == "success" for tc in completed):
        if has_irreversible_tool(state):
            config = state.get("config")
            if config and config.system_confirmed:
                return "synthesize"
            return "reflect"
        logger.info(f"[Graph] All tools succeeded → fast synthesize")
        return "synthesize"

    return "plan"


def after_reflect(state: AgentState) -> str:
    """Route after reflection."""
    wall_clock_start = state.get("wall_clock_start")
    if wall_clock_start:
        elapsed = time.time() - wall_clock_start
        slo = SLO_THRESHOLDS.get(state.get("complexity"), 10.0)
        if elapsed > slo * 0.8:
            logger.warning(f"[SLO] Skipping to respond ({elapsed:.1f}s)")
            return "respond"

    if state.get("needs_replanning"):
        config = state.get("config")
        max_iter = config.max_iterations if config else 5
        iteration = state.get("iteration", 0)
        if iteration < max_iter:
            return "plan"

    complexity = state.get("complexity")
    if complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL):
        if get_completed_tools(state):
            return "critic"

    return "respond"


def after_error(state: AgentState) -> str:
    """Route after error recovery."""
    if not state.get("error"):
        config = state.get("config")
        max_iter = config.max_iterations if config else 5
        if state.get("iteration", 0) >= max_iter:
            return "respond"
        return "plan"

    recovery_level = state.get("error_recovery_level", 0)
    if recovery_level >= 2:
        logger.warning("[Graph] Error recovery exhausted")
    return "respond"


def after_router(state: AgentState) -> str:
    """Route after intent classification."""
    complexity = state.get("complexity")

    if complexity == QueryComplexity.SIMPLE:
        return "simple_respond"

    agent_code = state.get("agent_code", "")
    scene_code = state.get("scene_code", "")
    if agent_code and scene_code == "task_decompose":
        return "wbs_decompose"

    from app.core.config import settings
    if (
        complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL)
        and settings.LANGGRAPH_ENABLE_RAG_INJECT
    ):
        config = state.get("config")
        if config and config.enable_rag_inject:
            return "parallel_plan"

    return "plan"


def after_orchestrate(state: AgentState) -> str:
    """Route after multi-agent orchestration."""
    if state.get("error"):
        return "error"
    return "critic"


def after_critic(state: AgentState) -> str:
    """Route after critic evaluation."""
    wall_clock_start = state.get("wall_clock_start")
    if wall_clock_start:
        elapsed = time.time() - wall_clock_start
        slo = SLO_THRESHOLDS.get(state.get("complexity"), 10.0)
        if elapsed > slo * 0.9:
            logger.warning(f"[SLO] Force respond ({elapsed:.1f}s)")
            return "respond"

    if not state.get("critic_passed", True):
        config = state.get("config")
        max_iter = config.max_iterations if config else 5
        if state.get("iteration", 0) < max_iter:
            return "plan"
    return "respond"


def after_wbs(state: AgentState) -> str:
    """Route after WBS decomposition."""
    if state.get("error"):
        return "error"
    if state.get("wbs_structure"):
        return "orchestrate"
    return "plan"
