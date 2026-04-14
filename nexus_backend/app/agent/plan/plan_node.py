"""
Graph Node: plan_node — LLM planning with tool binding.

Orchestrator that delegates to sub-modules:
  - prompt_builder:     system prompt assembly
  - tool_binding:       tool binding decision
  - llm_caller:         LLM invocation + diagnostics
  - response_recovery:  fallback strategies
  - tool_parser:        tool call parsing + validation
  - self_consistency:   CRITICAL multi-sample voting
  - tracing:            decision logging
"""

import contextlib
import time

from langchain_core.runnables import RunnableConfig

from app.agent.node_helpers import (
    _ALWAYS_INCLUDE_TOOLS,
    AgentConfig,
    AgentPhase,
    AgentState,
    QueryComplexity,
    ThinkingStep,
    _get_tool_schemas,
    _messages_to_lc_format,
    logger,
    run_hooks,
)
from app.agent.plan.llm_caller import call_llm
from app.agent.plan.prompt_builder import inject_system_prompts
from app.agent.plan.response_recovery import recover_response
from app.agent.plan.tool_binding import bind_tools_to_llm
from app.agent.plan.tool_parser import parse_tool_calls
from app.agent.plan.tracing import log_decision


async def plan_node(state: AgentState, config: RunnableConfig | None = None) -> dict:
    """
    Call the LLM with the current messages + tool schemas.
    """
    # ── [A] State extraction ──
    agent_config: AgentConfig = state["config"]
    model = state.get("selected_model", agent_config.model)
    messages = state.get("messages", [])
    iteration = state.get("iteration", 0)
    rag_context = state.get("rag_context", "")

    # SLO tracking: record wall clock start on first iteration
    _wall_clock_extras = {}
    if iteration == 0 and not state.get("wall_clock_start"):
        _wall_clock_extras["wall_clock_start"] = time.time()

    # Lifecycle Hook: before_prompt_build
    hook_ctx = await run_hooks(
        "before_prompt_build",
        {
            "messages": messages,
            "model": model,
            "iteration": iteration,
            "rag_context": rag_context,
            "user_id": agent_config.user_id,
            "scene_code": state.get("scene_code", ""),
        },
    )
    if hook_ctx:
        messages = hook_ctx.get("messages", messages)
        rag_context = hook_ctx.get("rag_context", rag_context)

    # ── [B] Model resolution ──
    resolved = None
    complexity = state.get("complexity", QueryComplexity.MODERATE)

    # Auto-detect tier when router didn't explicitly set complexity (default MODERATE)
    if complexity == QueryComplexity.MODERATE and "complexity" not in state:
        try:
            from app.services.llm_helpers import auto_detect_tier

            tool_schemas_for_tier = _get_tool_schemas(
                agent_config.user_role, scene_code=state.get("scene_code")
            )
            detected_tier = auto_detect_tier(
                messages=messages,
                tools_count=len(tool_schemas_for_tier) if tool_schemas_for_tier else 0,
                scene_code=state.get("scene_code", ""),
                iteration=iteration,
            )
            _tier_to_complexity = {
                "economy": QueryComplexity.SIMPLE,
                "balanced": QueryComplexity.MODERATE,
                "power": QueryComplexity.COMPLEX,
                "flagship": QueryComplexity.CRITICAL,
            }
            complexity = _tier_to_complexity.get(detected_tier, complexity)
            logger.debug(
                "Auto-detected tier=%s → complexity=%s", detected_tier, complexity.value
            )
        except Exception:
            pass  # Fall through to default MODERATE

    if agent_config.resolved_configs:
        resolved = agent_config.resolved_configs.get(complexity.model_tier)
    if not resolved:
        try:
            from app.services.llm_helpers import resolve_model_config

            org_id = agent_config.org_id or "default"
            scene_code = state.get("scene_code", "")
            agent_code = state.get("agent_code", "")
            resolved = await resolve_model_config(
                org_id, scene_code, agent_code, complexity_tier=complexity.model_tier
            )
        except Exception:
            logger.debug(
                "LLM gateway model config unavailable in plan_node, using default"
            )

    # ── [C] Convert to LC format ──
    lc_msgs = _messages_to_lc_format(messages)

    # Prompt Compression
    try:
        from app.agent.prompt_compression import compress_conversation_history

        lc_msgs = await compress_conversation_history(
            lc_msgs,
            max_tokens=6000,
            model=agent_config.mini_model,
            max_turns=8,
            keep_recent=3,
        )
    except Exception as e:
        logger.error(f"[PlanNode] Prompt compression failed, using full history: {e}")

    # ── [D]+[E]+[F] System prompt injection ──
    intent_summary = state.get("intent_summary", "")
    lc_msgs = await inject_system_prompts(
        lc_msgs,
        state=state,
        agent_config=agent_config,
        complexity=complexity,
        intent_summary=intent_summary,
        iteration=iteration,
        rag_context=rag_context,
    )

    # ── [G] Tool binding ──
    # Re-read complexity in case it was shadowed (original code did this)
    complexity = state.get("complexity", QueryComplexity.MODERATE)
    _configurable_early = (
        (config or {}).get("configurable", {}) if isinstance(config, dict) else {}
    )
    _trace_id = _configurable_early.get("trace_id")

    # Extract last user message for embedding-based tool filtering
    _last_user_msg = ""
    for _m in reversed(messages):
        _content = getattr(_m, "content", None) or (
            _m.get("content") if isinstance(_m, dict) else ""
        )
        _role = getattr(_m, "role", None) or (
            _m.get("role") if isinstance(_m, dict) else ""
        )
        if _role == "user" and _content:
            _last_user_msg = _content[:200]
            break

    llm, bind_kwargs = await bind_tools_to_llm(
        agent_config=agent_config,
        model=model,
        state=state,
        complexity=complexity,
        intent_summary=intent_summary,
        iteration=iteration,
        resolved=resolved,
        trace_id=_trace_id,
        user_query=_last_user_msg or intent_summary,
    )

    thinking_step = ThinkingStep(
        phase=AgentPhase.PLANNING.value,
        content=f"正在分析意图并规划执行路径... (轮次 {iteration + 1})",
    )

    # ── [H]+[I] LLM call + diagnostics ──
    llm_result = await call_llm(
        llm=llm,
        lc_msgs=lc_msgs,
        agent_config=agent_config,
        model=model,
        state=state,
        complexity=complexity,
        iteration=iteration,
        resolved=resolved,
        config=config,
    )
    if llm_result.error_result:
        return llm_result.error_result

    ai_msg = llm_result.ai_msg
    input_tokens = llm_result.input_tokens
    output_tokens = llm_result.output_tokens

    # ── [J] Response recovery ──
    # Prepare tool_schemas for recovery
    if complexity == QueryComplexity.SIMPLE:
        tool_schemas = [
            s
            for s in _get_tool_schemas(
                agent_config.user_role, scene_code=state.get("scene_code")
            )
            if s["function"]["name"] in _ALWAYS_INCLUDE_TOOLS
        ] or None
    else:
        tool_schemas = _get_tool_schemas(
            agent_config.user_role,
            intent_summary=state.get("intent_summary", ""),
            scene_code=state.get("scene_code"),
            intent_domains=state.get("intent_domains"),
        )

    ai_msg, content, tool_calls_raw = await recover_response(
        ai_msg=ai_msg,
        state=state,
        agent_config=agent_config,
        model=model,
        lc_msgs=lc_msgs,
        tool_schemas=tool_schemas,
        complexity=complexity,
        iteration=iteration,
        resolved=resolved,
    )

    # ── [K] Tool call parsing ──
    pending_tools, validation_error = parse_tool_calls(
        tool_calls_raw,
        content=content,
        agent_config=agent_config,
        iteration=iteration,
        state=state,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        thinking_step=thinking_step,
    )
    if validation_error:
        return validation_error

    # ── [L] Result assembly ──
    _decomp_done = state.get("_task_decomposition_done", False)
    _task_steps = state.get("_task_steps", [])
    _active_idx = state.get("_active_step_index", 0)

    # Parse task decomposition from LLM response
    _new_task_steps = None
    if (
        iteration == 0
        and not _decomp_done
        and complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL)
        and content
        and "task_steps" in content
    ):
        import json as _json
        import re as _re

        json_match = _re.search(
            r"```json\s*(\{.*?\"task_steps\".*?\})\s*```", content, _re.DOTALL
        )
        if json_match:
            try:
                parsed = _json.loads(json_match.group(1))
                steps = parsed.get("task_steps", [])
                if isinstance(steps, list) and 2 <= len(steps) <= 8:
                    _new_task_steps = steps
                    content = (
                        content[: json_match.start()] + content[json_match.end() :]
                    )
                    content = content.strip()
                    logger.info(
                        f"[PlanNode] Task decomposed into {len(steps)} steps: {[s.get('title') for s in steps]}"
                    )
            except (_json.JSONDecodeError, KeyError):
                pass

    # Construct result dict
    result = {
        "messages": [ai_msg],
        "current_phase": (
            AgentPhase.EXECUTING if pending_tools else AgentPhase.REFLECTING
        ),
        "plan": content or "(执行工具调用)",
        "requires_tools": bool(pending_tools),
        "pending_tool_calls": pending_tools,
        "thinking_steps": [thinking_step],
        "total_input_tokens": state.get("total_input_tokens", 0) + input_tokens,
        "total_output_tokens": state.get("total_output_tokens", 0) + output_tokens,
    }

    # Explainability: log plan outcome decision
    log_decision(
        _trace_id,
        step_id=f"plan_outcome_iter{iteration}",
        decision=(
            f"tools={[t.tool_name for t in pending_tools]}"
            if pending_tools
            else "direct_response"
        ),
        reasoning=(
            f"LLM规划了{len(pending_tools)}个工具调用"
            if pending_tools
            else f"LLM直接回复(无工具), 内容长度={len(content)}"
        ),
    )

    # ToT: Store self-consistency candidates for backtracking
    if llm_result.sc_succeeded and llm_result.sc_candidates:
        result["candidate_plans"] = llm_result.sc_candidates
        result["best_plan_score"] = 1.0 - max(
            (c.get("score", 0) for c in llm_result.sc_candidates), default=0
        )
        result["backtrack_depth"] = 0

    # Store task decomposition in state
    if _new_task_steps:
        result["_task_decomposition_done"] = True
        result["_task_steps"] = _new_task_steps
        result["_active_step_index"] = 0
        result["thinking_steps"] = [
            thinking_step,
            ThinkingStep(
                phase=AgentPhase.PLANNING.value,
                content=f"任务已分解为 {len(_new_task_steps)} 个步骤: {', '.join(s.get('title', '') for s in _new_task_steps)}",
            ),
        ]
    elif _decomp_done and _task_steps and _active_idx < len(_task_steps):
        reflection_guidance = state.get("reflection_guidance", "")
        is_step_retry = (
            "未完成" in reflection_guidance
            and f"步骤 {_active_idx + 1}" in reflection_guidance
        )
        if not is_step_retry:
            result["_active_step_index"] = _active_idx + 1
            if _active_idx + 1 >= len(_task_steps):
                result["thinking_steps"] = [
                    thinking_step,
                    ThinkingStep(
                        phase=AgentPhase.PLANNING.value,
                        content=f"所有 {len(_task_steps)} 个步骤已完成，正在生成最终回复",
                    ),
                ]
        else:
            logger.info(f"[PlanNode] Step {_active_idx + 1} retry, not advancing index")

    if pending_tools:
        tool_names = ", ".join(t.tool_name for t in pending_tools)
        exec_step = ThinkingStep(
            phase=AgentPhase.PLANNING.value,
            content=f"计划调用工具: {tool_names}",
        )
        result["thinking_steps"] = [thinking_step, exec_step]
        # Langfuse: log tool plans
        _configurable = (
            (config or {}).get("configurable", {}) if isinstance(config, dict) else {}
        )
        trace_logger = _configurable.get("trace_logger")
        if trace_logger:
            for t in pending_tools:
                with contextlib.suppress(Exception):
                    trace_logger.log_tool_plan(t.tool_name, t.tool_args)

    # Merge SLO wall clock start into result
    if _wall_clock_extras:
        result.update(_wall_clock_extras)

    return result
