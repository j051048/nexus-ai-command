"""
LangGraph State Machine — wires the nodes together with conditional edges.

Graph topology:

    ┌─────────┐
    │  START  │
    └────┬────┘
         │
    ┌────▼─────┐
    │  Router  │  ← classify intent, pick model, detect VMD role
    └────┬─────┘
         │
    ┌────▼──────────┐
    │ after_router  │  ← conditional: simple / multi-agent / standard / parallel?
    └─┬───┬───┬──┬──┘
      │   │   │  │
  ┌───▼┐  │   │ ┌▼────────────┐
  │Smpl│  │   │ │ WBS Decomp  │  ← multi-agent path
  │Rspd│  │   │ └─────┬───────┘
  └─┬──┘  │   │       │
    │  ┌──▼─┐ │ ┌─────▼───────┐
    │  │Plan│ │ │ Orchestrate  │
    │  └──┬─┘ │ └─────┬───────┘
    │     │   │       │
    │     │  ┌▼──────────────┐
    │     │  │Parallel Plan  │  ← RAG + Plan in parallel (COMPLEX + RAG)
    │     │  └───────┬───────┘
    │     │          │
    │  ┌──▼──────────▼──┐
    │  │    Execute     │
    │  └───────┬────────┘
    │          │
    │  ┌───▼──────┐
    │  │Synthesize│    ← all tools OK: fast path (skips reflect+critic)
    │  └───┬──────┘
    │      │
    │  ┌───▼───┐  ┌────▼───┐
    │  │Respond│  │Respond │  ← all paths converge
    │  └───┬───┘  └────┬───┘
    │      │           │
    │  ┌───▼───┐  ┌────▼───┐
    │  │  END  │  │  END   │
    │  └───────┘  └────────┘
    │
  ┌──▼───┐
  │ END  │
  └──────┘

Architecture Evolution Roadmap (2026-03):
  Current: Flat graph with WBS decomposition for multi-agent scenarios.
  Future:  Supervisor-Worker pattern (LangGraph multi-agent) where director_agent
           acts as a true supervisor node that dynamically spawns worker sub-graphs
           (content_agent, media_agent, etc.) and aggregates their results.
           This enables true parallel sub-agent execution, independent retries,
           and cleaner state isolation per worker.
"""

import hashlib
import json
import logging
import time
from typing import Optional

from langgraph.graph import END, StateGraph

from app.agent.checkpointer import get_checkpointer
from app.agent.nodes import critic_node, error_node, execute_node, plan_node, reflect_node, respond_node, simple_respond_node, synthesize_node
from app.agent.node_parallel_context import parallel_context_and_plan
from app.agent.nodes_orchestrator import orchestrate_node
from app.agent.nodes_wbs import wbs_decompose_node
from app.agent.router import route_node
from app.agent.state import AgentState, QueryComplexity
from app.core.config import settings
from app.tools import get_tool

logger = logging.getLogger(__name__)

# Track tool schema version for hot-reload
_tool_schema_version = 0


def get_tool_schema_version() -> int:
    """Get current tool schema version."""
    return _tool_schema_version


def increment_tool_schema_version():
    """Increment tool schema version (call when tools are reloaded)."""
    global _tool_schema_version
    _tool_schema_version += 1
    logger.info(f"[Graph] Tool schema version incremented to {_tool_schema_version}")


# ─── Loop Detection (inspired by OpenClaw tool-loop-detection.ts) ────────────

# Sliding window size for tool call history analysis
_LOOP_WINDOW_SIZE = 30
# Thresholds for different detection strategies
_GENERIC_REPEAT_THRESHOLD = 3     # Same tool+args N times → force reflect
_POLL_NO_PROGRESS_THRESHOLD = 5   # Polling tools with no progress → block
_GLOBAL_CIRCUIT_BREAKER = 15      # Absolute safety net: any single tool N times → block

# Tools known to cause polling loops (status checks, process waits)
_POLL_TOOLS: set[str] = {
    "get_company_stats", "query_leave_status", "query_expense_status",
    "query_attendance", "get_pending_approvals",
}


def _tool_call_fingerprint(tool_calls: list) -> str:
    """Generate a hash fingerprint for a set of tool calls (name + args)."""
    if not tool_calls:
        return ""
    parts = []
    for tc in sorted(tool_calls, key=lambda t: t.tool_name):
        args_str = json.dumps(tc.tool_args, sort_keys=True, ensure_ascii=False) if tc.tool_args else ""
        parts.append(f"{tc.tool_name}:{args_str}")
    combined = "|".join(parts)
    return hashlib.md5(combined.encode()).hexdigest()


def _detect_loop(state: AgentState) -> bool:
    """
    Multi-strategy loop detection (4 detectors, inspired by OpenClaw).

    1. Generic Repeat: same tool+args fingerprint N times consecutively
    2. Known Poll No-Progress: polling tools called repeatedly
    3. Ping-Pong: A-B-A-B alternating pattern
    4. Global Circuit Breaker: any single tool exceeds absolute limit
    """
    history = state.get("_tool_call_history", [])
    if len(history) < 2:
        return False

    window = history[-_LOOP_WINDOW_SIZE:]

    # --- Detector 1: Generic Repeat (same fingerprint N consecutive times) ---
    if len(window) >= _GENERIC_REPEAT_THRESHOLD:
        recent = window[-_GENERIC_REPEAT_THRESHOLD:]
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
    completed = state.get("completed_tool_calls", [])
    if completed:
        recent_completed = completed[-_LOOP_WINDOW_SIZE:]
        for poll_tool in _POLL_TOOLS:
            count = sum(1 for tc in recent_completed if tc.tool_name == poll_tool)
            if count >= _POLL_NO_PROGRESS_THRESHOLD:
                logger.warning(f"[LoopDetect] Poll no-progress: {poll_tool} called {count} times")
                return True

    # --- Detector 4: Global Circuit Breaker ---
    if completed:
        recent_completed = completed[-_LOOP_WINDOW_SIZE:]
        from collections import Counter
        tool_counts = Counter(tc.tool_name for tc in recent_completed)
        for tool_name, count in tool_counts.items():
            if count >= _GLOBAL_CIRCUIT_BREAKER:
                logger.warning(f"[LoopDetect] Circuit breaker: {tool_name} called {count} times")
                return True

    return False


# ─── Mutation Fast-Path Helper ───────────────────────────────────────────────


def _has_irreversible_tool(state_or_dict: dict) -> bool:
    """
    Check if any completed tool call used an irreversible (high-risk) tool.

    G1: Irreversible tools (financial approvals, destructive ops, etc.) must
    always go through Critic review — they should NEVER take a fast path.
    """
    completed = state_or_dict.get("completed_tool_calls", [])
    for tc in completed:
        tool = get_tool(getattr(tc, "tool_name", "") or tc.get("tool_name", ""))
        if tool and tool.is_irreversible:
            return True
    return False


def _is_mutation_fast_path(state_or_dict: dict) -> bool:
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
    if _has_irreversible_tool(state_or_dict):
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


# ─── Conditional Edge Functions ──────────────────────────────────────────────


def _after_plan(state: AgentState) -> str:
    """
    After planning:
      - If error occurred → error
      - If tool calls are pending → execute
      - SIMPLE queries skip reflection → respond directly
      - MODERATE with no tools (direct text answer) → respond directly
      - Mutation fast-path: all tools succeeded & irreversible → respond directly
      - Otherwise → reflect (validates the direct answer)
    """
    if state.get("error"):
        return "error"
    if state.get("requires_tools") and state.get("pending_tool_calls"):
        return "execute"
    # Short-circuit: SIMPLE queries (greetings, FAQ) skip reflection
    if state.get("complexity") == QueryComplexity.SIMPLE:
        return "respond"
    # Item 33: Reflection budget — skip reflect when budget exhausted
    reflection_count = state.get("reflection_count", 0)
    if reflection_count >= 2:
        logger.info(f"[Graph] Reflection budget exhausted ({reflection_count}/2), skipping to respond")
        return "respond"
    # MODERATE with direct text (no tools needed) — skip reflect for speed
    if state.get("complexity") == QueryComplexity.MODERATE and not state.get("completed_tool_calls"):
        return "respond"
    # Fast-path: mutation-only tools with all-success → skip reflect+critic
    if _is_mutation_fast_path(state):
        logger.info("[Graph] Mutation fast-path: all tools succeeded & irreversible, skipping reflect+critic")
        return "respond"
    return "reflect"


def _after_execute(state: AgentState) -> str:
    """
    After execution:
      - If error occurred → error
      - If confirmation pending (tool blocked by HITL gate) → respond (stop graph)
      - If loop detected (same tools called repeatedly) → reflect to finalize
      - SIMPLE/MODERATE with all tools successful → synthesize (lightweight, 1 LLM call)
      - Otherwise → plan (full second-pass with bind_tools for potential follow-up)
      - Guard: if iteration limit reached → reflect to finalize.

    P2 Enhancement: Rich observation logging for debugging and model awareness.
    """
    if state.get("error"):
        return "error"

    # HITL: When tools are blocked for confirmation, stop the graph immediately
    # so the stream layer can emit SSE confirmation events to the frontend.
    if state.get("confirmation_pending"):
        logger.info("[Graph] Confirmation pending, routing to respond (HITL gate)")
        return "respond"

    config = state.get("config")
    max_iter = config.max_iterations if config else 5
    iteration = state.get("iteration", 0)

    # P2: Rich observation layer — log comprehensive state for debugging
    completed = state.get("completed_tool_calls", [])
    tool_summary = ", ".join(
        f"{getattr(tc, 'tool_name', '?')}={'ok' if getattr(tc, 'status', '') == 'success' else getattr(tc, 'status', '?')}"
        for tc in completed[-5:]  # last 5 tools
    ) if completed else "none"
    complexity = state.get("complexity")
    logger.info(
        f"[Graph:Observe] after_execute: iter={iteration}/{max_iter} "
        f"complexity={complexity} tools=[{tool_summary}] "
        f"pending={len(state.get('pending_tool_calls', []))} "
        f"has_plan={'yes' if state.get('plan') else 'no'}"
    )

    if iteration >= max_iter:
        logger.warning(f"[Graph] Max iterations ({max_iter}) reached, forcing reflect")
        state["circuit_break_reason"] = "max_iterations"
        return "reflect"

    # P2: Loop detection — prevent infinite plan→execute→plan cycles
    if _detect_loop(state):
        logger.warning(
            f"[Graph] Loop detected after {iteration} iterations "
            f"(same tool calls repeated {_GENERIC_REPEAT_THRESHOLD}x), forcing reflect"
        )
        # Set structured circuit break reason for frontend event
        state["circuit_break_reason"] = "loop_detected"
        # Persist loop failure for analytics
        try:
            import asyncio
            from app.services.failure_log_service import failure_log_service

            config = state.get("config")
            user_message = ""
            for msg in reversed(state.get("messages", [])):
                if hasattr(msg, "type") and msg.type == "human":
                    user_message = msg.content
                    break
            asyncio.create_task(failure_log_service.log_failure(
                org_id=getattr(config, "org_id", None) if config else None,
                user_id=getattr(config, "user_id", None) if config else None,
                user_message=user_message or "loop detected",
                intent_summary=state.get("intent_summary"),
                complexity=state.get("complexity", "").value if state.get("complexity") else None,
                error_type="loop",
                error_detail=f"Loop after {iteration} iterations",
                severity="medium",
            ))
        except Exception:
            pass
        return "reflect"

    # Fast synthesis: when all tools succeeded, use lightweight synthesize_node
    # instead of full plan second-pass. Saves ~60% tokens.
    # - SIMPLE/MODERATE: skip reflect+critic entirely
    # - COMPLEX/CRITICAL: embed critic self-evaluation in synthesis prompt,
    #   eliminating separate critic_node LLM call (3→2 LLM calls)
    # G1: irreversible tools MUST go through reflect→critic, never fast synthesize
    complexity = state.get("complexity")
    completed = state.get("completed_tool_calls", [])
    if (
        completed
        and all(
            (getattr(tc, "status", None) or tc.get("status")) == "success"
            for tc in completed
        )
    ):
        if _has_irreversible_tool(state):
            logger.info(
                "[Graph] All tools succeeded but irreversible tool detected → reflect (G1: Critic review required)"
            )
            return "reflect"
        logger.info(f"[Graph] All tools succeeded + {complexity} → fast synthesize")
        return "synthesize"

    # Some tools failed → back to plan with structured error guidance
    failed_tools = [
        tc for tc in completed
        if (getattr(tc, "status", None) or tc.get("status")) == "error"
    ]
    if failed_tools:
        lines = ["以下工具执行失败，请根据错误类型调整策略："]
        for ft in failed_tools[:5]:
            name = getattr(ft, "tool_name", None) or ft.get("tool_name", "unknown")
            result = (getattr(ft, "result", "") or ft.get("result", "") or "")[:300]
            err_type = getattr(ft, "error_type", None) or ft.get("error_type", "unknown")
            if err_type == "param_error":
                lines.append(f"- {name} [参数错误]: {result}")
                lines.append("  -> 检查参数格式和必填字段，修正后重试")
            elif err_type == "fatal":
                lines.append(f"- {name} [不可恢复]: {result}")
                lines.append("  -> 此工具无法完成目标，换用其他工具或改变方案")
            else:
                lines.append(f"- {name} [临时故障]: {result}")
                lines.append("  -> 网络/服务问题，可直接重试")
        state["reflection_guidance"] = "\n".join(lines)

    return "plan"


def _proactive_compress(state: AgentState) -> None:
    """Proactively micro-compact messages mid-reasoning to save tokens.

    Called when iteration >= 3 during replanning loops. Uses sync-safe
    micro-compaction (no LLM call) to shrink tool outputs and long messages.
    """
    from app.agent.prompt_compression import _micro_compact_lc_messages

    messages = state.get("messages", [])
    if len(messages) < 6:
        return
    compacted = _micro_compact_lc_messages(messages)
    state["messages"] = compacted
    logger.info(f"[Graph] Proactive mid-reasoning compress applied ({len(messages)} messages)")


# ── SLO thresholds (seconds) per complexity level ──
_SLO_THRESHOLDS = {
    QueryComplexity.SIMPLE: 5.0,
    QueryComplexity.MODERATE: 10.0,
    QueryComplexity.COMPLEX: 20.0,
    QueryComplexity.CRITICAL: 30.0,
}


def _after_reflect(state: AgentState) -> str:
    """
    After reflection:
      - If needs_replanning (hallucination detected) → back to plan
      - COMPLEX/CRITICAL with tool results (reflect skipped LLM layers) → critic
      - COMPLEX/CRITICAL without tools (reflect already did LLM check) → respond (skip critic)
      - Otherwise → respond (finalize)

    P2 Enhancement: Observation logging + iteration guard on replanning.
    """
    # Dynamic SLO degradation: skip expensive downstream nodes if running out of time
    wall_clock_start = state.get("wall_clock_start")
    if wall_clock_start:
        elapsed = time.time() - wall_clock_start
        slo = _SLO_THRESHOLDS.get(state.get("complexity"), 10.0)
        if elapsed > slo * 0.8:
            logger.warning(f"[SLO] after_reflect: {elapsed:.1f}s > 80% of {slo}s, skipping to respond")
            return "respond"

    needs_replan = state.get("needs_replanning")
    complexity = state.get("complexity")
    confidence = state.get("confidence_score", 0.0)
    completed_tools = state.get("completed_tool_calls", [])

    logger.info(
        f"[Graph:Observe] after_reflect: needs_replan={needs_replan} "
        f"complexity={complexity} confidence={confidence:.2f} "
        f"tools_used={len(completed_tools)} "
        f"is_hallucination={state.get('is_hallucination', False)}"
    )

    if needs_replan:
        config = state.get("config")
        max_iter = config.max_iterations if config else 5
        iteration = state.get("iteration", 0)
        if iteration < max_iter:
            # Proactive compression: shrink messages mid-reasoning to save tokens
            if iteration >= 3:
                _proactive_compress(state)
            return "plan"
        logger.warning("[Graph] Needs replanning but max iterations reached, responding anyway")

    # P1-5: Route COMPLEX/CRITICAL through critic, but only when reflect
    # skipped its LLM layers (i.e., tools were involved). When reflect
    # already did LLM-based fact-checking, the extra critic call is redundant.
    complexity = state.get("complexity")

    # P1: Task decomposition — check step acceptance before advancing
    _task_steps = state.get("_task_steps", [])
    _active_idx = state.get("_active_step_index", 0)
    if _task_steps and _active_idx < len(_task_steps):
        current_step = _task_steps[_active_idx]
        criteria = current_step.get("acceptance_criteria", "")

        # Rule-based check: did any tool succeed in this step?
        completed_tools = state.get("completed_tool_calls", [])
        has_success = any(
            (getattr(tc, "status", None) or tc.get("status")) == "success"
            for tc in completed_tools
        )
        has_failure = any(
            (getattr(tc, "status", None) or tc.get("status")) == "error"
            for tc in completed_tools
        )

        if has_failure and not has_success:
            # Step not met: all tools failed, retry without advancing
            logger.info(
                f"[Graph] Step {_active_idx + 1}/{len(_task_steps)} not met: "
                f"all tools failed, retrying without advancing"
            )
            state["reflection_guidance"] = (
                f"步骤 {_active_idx + 1}「{current_step.get('title', '')}」未完成: "
                f"工具调用全部失败。"
                + (f"\n验收标准: {criteria}" if criteria else "")
                + "\n请分析失败原因，修正参数或换用其他工具重试此步骤。"
            )
            state["needs_replanning"] = False
            return "plan"

        logger.info(
            f"[Graph] Task decomposition: step {_active_idx + 1}/{len(_task_steps)} "
            f"{'passed' if has_success else 'no tools needed'}, advancing to next"
        )
        return "plan"

    if complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL):
        completed_tools = state.get("completed_tool_calls", [])
        if completed_tools:
            # Tools were used → reflect skipped Layer 4/5, critic needed
            return "critic"
        # No tools → reflect already did thorough LLM check, skip critic

    return "respond"


def _after_error(state: AgentState) -> str:
    """
    After error recovery attempt:
      - If recovery worked (error cleared) → plan
      - If max recovery level reached → respond (graceful degradation)
      - Otherwise → respond (with error message)

    P2 Enhancement: Multi-level fallback with observation logging.
    """
    error = state.get("error")
    recovery_level = state.get("error_recovery_level", 0)
    iteration = state.get("iteration", 0)
    config = state.get("config")
    max_iter = config.max_iterations if config else 5

    logger.info(
        f"[Graph:Observe] after_error: error={'yes' if error else 'cleared'} "
        f"recovery_level={recovery_level} iter={iteration}/{max_iter}"
    )

    if not error:
        # Recovery succeeded — but guard against infinite recovery loops
        if iteration >= max_iter:
            logger.warning("[Graph] Error cleared but max iterations reached, responding")
            return "respond"
        return "plan"

    # P2: Graduated fallback — don't give up on first error
    # Level 0→1: first error, try recovery (already attempted by error_node)
    # Level 2+: recovery exhausted, respond with best-effort
    if recovery_level >= 2:
        logger.warning(
            f"[Graph] Error recovery exhausted (level={recovery_level}), "
            f"responding with graceful degradation"
        )
    return "respond"


def _after_router(state: AgentState) -> str:
    """
    After routing:
      - SIMPLE queries → simple_respond (fast-path, skip Plan→Execute→Reflect)
      - If the router detected a multi-agent orchestration scenario → wbs_decompose
      - COMPLEX/CRITICAL with RAG enabled → parallel_context_and_plan
      - Otherwise → plan (standard single-agent flow)

    P2 Enhancement: Observation logging for routing decisions.
    """
    # SIMPLE fast-path: greetings/chitchat → direct mini_model response
    complexity = state.get("complexity")
    intent = state.get("intent_summary", "")
    agent_code = state.get("agent_code", "")
    scene_code = state.get("scene_code", "")

    logger.info(
        f"[Graph:Observe] after_router: complexity={complexity} "
        f"intent='{intent[:50]}' agent={agent_code or 'none'} "
        f"scene={scene_code or 'none'} "
        f"model={state.get('selected_model', '?')}"
    )

    if complexity == QueryComplexity.SIMPLE:
        return "simple_respond"

    # Check if this needs multi-agent WBS decomposition
    if agent_code and scene_code == "task_decompose":
        return "wbs_decompose"

    # Parallel optimization: for COMPLEX/CRITICAL queries with RAG enabled,
    # run context retrieval concurrently with planning
    if (
        complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL)
        and settings.LANGGRAPH_ENABLE_RAG_INJECT
    ):
        config = state.get("config")
        if config and config.enable_rag_inject:
            return "parallel_plan"

    return "plan"


def _after_orchestrate(state: AgentState) -> str:
    """
    After orchestration:
      - If error occurred → error
      - Otherwise → critic (P1-5: quality gate before respond)
    """
    if state.get("error"):
        return "error"
    return "critic"


def _after_critic(state: AgentState) -> str:
    """
    P1-5: After critic evaluation:
      - If critic passed → respond
      - If critic failed → plan (one correction pass, guarded by max_iterations)
    """
    # Dynamic SLO degradation: even if critic failed, respond if close to SLO
    wall_clock_start = state.get("wall_clock_start")
    if wall_clock_start:
        elapsed = time.time() - wall_clock_start
        slo = _SLO_THRESHOLDS.get(state.get("complexity"), 10.0)
        if elapsed > slo * 0.9:
            logger.warning(f"[SLO] after_critic: {elapsed:.1f}s > 90% of {slo}s, force respond")
            return "respond"

    if not state.get("critic_passed", True):
        config = state.get("config")
        max_iter = config.max_iterations if config else 5
        iteration = state.get("iteration", 0)
        if iteration < max_iter:
            return "plan"
        logger.warning("[Graph] Critic failed but max iterations reached, responding anyway")
    return "respond"


def _after_wbs(state: AgentState) -> str:
    """
    After WBS decomposition:
      - If error occurred → error
      - If wbs_structure is ready → orchestrate
      - Fallback → plan (degrade to single-agent)
    """
    if state.get("error"):
        return "error"
    if state.get("wbs_structure"):
        return "orchestrate"
    # Fallback to standard planning if WBS fails silently
    return "plan"


# ─── Graph Builder ───────────────────────────────────────────────────────────


def build_agent_graph() -> StateGraph:
    """
    Construct the LangGraph state machine.
    Returns an uncompiled StateGraph.

    Includes both the standard single-agent flow and the VMD multi-agent
    orchestration path (WBS decompose → orchestrate → respond).
    """
    graph = StateGraph(AgentState)

    # ── Add Nodes ──
    graph.add_node("router", route_node)
    graph.add_node("plan", plan_node)
    graph.add_node("parallel_plan", parallel_context_and_plan)  # RAG + Plan in parallel
    graph.add_node("execute", execute_node)
    graph.add_node("reflect", reflect_node)
    graph.add_node("respond", respond_node)
    graph.add_node("simple_respond", simple_respond_node)  # SIMPLE fast-path
    graph.add_node("synthesize", synthesize_node)  # Single-tool fast synthesis
    graph.add_node("error", error_node)
    # VMD multi-agent nodes
    graph.add_node("wbs_decompose", wbs_decompose_node)
    graph.add_node("orchestrate", orchestrate_node)
    # P1-5: Independent quality evaluator
    graph.add_node("critic", critic_node)

    # ── Set Entry Point ──
    graph.set_entry_point("router")

    # ── Add Edges ──
    # router → plan | parallel_plan | wbs_decompose | simple_respond (conditional)
    graph.add_conditional_edges(
        "router",
        _after_router,
        {
            "plan": "plan",
            "parallel_plan": "parallel_plan",
            "wbs_decompose": "wbs_decompose",
            "simple_respond": "simple_respond",
        },
    )

    # wbs_decompose → orchestrate | error | plan (conditional)
    graph.add_conditional_edges(
        "wbs_decompose",
        _after_wbs,
        {
            "orchestrate": "orchestrate",
            "error": "error",
            "plan": "plan",
        },
    )

    # orchestrate → critic | error (conditional, P1-5)
    graph.add_conditional_edges(
        "orchestrate",
        _after_orchestrate,
        {
            "critic": "critic",
            "error": "error",
        },
    )

    # plan → execute | reflect | respond | error (conditional)
    graph.add_conditional_edges(
        "plan",
        _after_plan,
        {
            "execute": "execute",
            "reflect": "reflect",
            "respond": "respond",
            "error": "error",
        },
    )

    # parallel_plan → execute | reflect | respond | error (same edges as plan)
    graph.add_conditional_edges(
        "parallel_plan",
        _after_plan,
        {
            "execute": "execute",
            "reflect": "reflect",
            "respond": "respond",
            "error": "error",
        },
    )

    # execute → plan | synthesize | reflect | respond | error (conditional)
    graph.add_conditional_edges(
        "execute",
        _after_execute,
        {
            "plan": "plan",
            "synthesize": "synthesize",
            "reflect": "reflect",
            "respond": "respond",
            "error": "error",
        },
    )

    # reflect → plan | respond | critic (conditional, P1-5)
    graph.add_conditional_edges(
        "reflect",
        _after_reflect,
        {
            "plan": "plan",
            "respond": "respond",
            "critic": "critic",
        },
    )

    # P1-5: critic → respond | plan (conditional)
    graph.add_conditional_edges(
        "critic",
        _after_critic,
        {
            "respond": "respond",
            "plan": "plan",
        },
    )

    # error → plan | respond (conditional)
    graph.add_conditional_edges(
        "error",
        _after_error,
        {
            "plan": "plan",
            "respond": "respond",
        },
    )

    # respond → END
    graph.add_edge("respond", END)

    # simple_respond → END (fast-path)
    graph.add_edge("simple_respond", END)

    # synthesize → respond (lightweight synthesis feeds into respond for output formatting)
    graph.add_edge("synthesize", "respond")

    return graph


class AgentGraph:
    """
    Singleton wrapper around the compiled LangGraph agent.

    Supports:
    - Lazy compilation with configurable checkpointer
    - Hot-reload when tools change
    - Thread-based conversation isolation

    Usage:
        agent = AgentGraph()
        result = await agent.run(initial_state, thread_id="...")
        # or
        async for event in agent.stream(initial_state, thread_id="..."):
            ...
    """

    _instance: Optional["AgentGraph"] = None
    _compiled = None
    _checkpointer = None
    _compiled_version = 0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._compiled = None
            cls._instance._checkpointer = None
            cls._instance._compiled_version = 0
        return cls._instance

    @property
    def compiled(self):
        """
        Lazy-compile the graph on first access.
        Auto-recompiles if tool schema version changed.
        Logs compilation duration for observability.
        """
        import time as _time

        current_version = get_tool_schema_version()

        if self._compiled is not None and self._compiled_version == current_version:
            return self._compiled

        if self._checkpointer is None:
            self._checkpointer = get_checkpointer()

        logger.info(f"[AgentGraph] Compiling LangGraph state machine (version {current_version})...")
        t0 = _time.monotonic()
        graph = build_agent_graph()

        # Compile with checkpointer for state persistence and HITL
        self._compiled = graph.compile(checkpointer=self._checkpointer)
        self._compiled_version = current_version
        elapsed_ms = int((_time.monotonic() - t0) * 1000)

        checkpointer_type = type(self._checkpointer).__name__
        logger.info(
            "[AgentGraph] Graph compiled with %s in %d ms (version %d)",
            checkpointer_type, elapsed_ms, current_version,
        )

        return self._compiled

    def reload(self):
        """
        Force recompilation of the graph.
        Call this when tools are dynamically added/removed.
        """
        self._compiled = None
        increment_tool_schema_version()
        logger.info("[AgentGraph] Graph marked for reload on next access")

    async def run(self, initial_state: AgentState, thread_id: str = "default") -> AgentState:
        """
        Run the graph to completion and return the final state.
        Suitable for non-streaming use cases (tests, batch jobs).
        """
        config = {
            "configurable": {
                "thread_id": thread_id,
            },
            "recursion_limit": settings.LANGGRAPH_MAX_ITERATIONS * 5 + 10,
        }
        return await self.compiled.ainvoke(initial_state, config=config)

    async def stream(self, initial_state: AgentState, thread_id: str = "default"):
        """
        Async generator that yields intermediate state updates.
        Each yielded item is a dict with the node name and state delta.
        """
        config = {
            "configurable": {
                "thread_id": thread_id,
            },
            "recursion_limit": settings.LANGGRAPH_MAX_ITERATIONS * 5 + 10,
        }
        async for event in self.compiled.astream(initial_state, config=config):
            yield event

    async def astream_events(
        self, initial_state: AgentState, thread_id: str = "default", version: str = "v2", config: dict | None = None
    ):
        """
        Async generator for granular events (token streaming, etc.).
        If config is provided, it will be merged with the default config.
        """
        base_config = {
            "configurable": {
                "thread_id": thread_id,
            },
            "recursion_limit": settings.LANGGRAPH_MAX_ITERATIONS * 5 + 10,
        }
        if config:
            # Merge configurable keys from caller (e.g. trace_logger)
            base_config["configurable"].update(config.get("configurable", {}))
        async for event in self.compiled.astream_events(initial_state, config=base_config, version=version):
            yield event

    async def get_state(self, thread_id: str) -> AgentState | None:
        """
        Retrieve the persisted state for a thread.
        Useful for resuming interrupted conversations.
        """
        config = {"configurable": {"thread_id": thread_id}}
        state_snapshot = await self.compiled.aget_state(config)
        return state_snapshot.values if state_snapshot else None

    async def update_state(self, thread_id: str, updates: dict):
        """
        Update the persisted state for a thread.
        Useful for human-in-the-loop confirmations.
        """
        config = {"configurable": {"thread_id": thread_id}}
        await self.compiled.aupdate_state(config, updates)


# Convenience function to get singleton
def get_agent_graph() -> AgentGraph:
    """Get the singleton AgentGraph instance."""
    return AgentGraph()


# ─── Cold Start Optimization ─────────────────────────────────────────────────
# Pre-compile graph at module load time so the first request doesn't pay
# the compilation cost. The AgentGraph singleton lazily compiles on first
# .compiled access, so we trigger that eagerly here.

_precompiled_graph: AgentGraph | None = None


def warmup_agent_graph() -> AgentGraph:
    """
    Eagerly compile the agent graph (called during app startup).
    Returns the warmed-up AgentGraph instance.
    Logs compilation duration for cold-start monitoring.
    """
    import time as _time

    global _precompiled_graph
    if _precompiled_graph is None:
        logger.info("[Graph] Warming up: pre-compiling agent graph at startup...")
        t0 = _time.monotonic()
        _precompiled_graph = get_agent_graph()
        # Trigger lazy compilation by accessing .compiled
        _ = _precompiled_graph.compiled
        elapsed_ms = int((_time.monotonic() - t0) * 1000)
        logger.info("[Graph] Warm-up complete: agent graph pre-compiled in %d ms", elapsed_ms)
    return _precompiled_graph
