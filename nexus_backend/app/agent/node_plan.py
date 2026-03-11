"""
Graph Node: plan_node — LLM planning with tool binding.
"""

import asyncio
import contextlib
import time

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from app.agent.node_helpers import (
    AgentConfig,
    AgentPhase,
    AgentState,
    QueryComplexity,
    ThinkingStep,
    ToolCallRecord,
    _ALWAYS_INCLUDE_TOOLS,
    _get_llm,
    _get_tool_schemas,
    _messages_to_lc_format,
    _try_extract_tool_names,
    get_tool,
    invoke_with_fallback,
    llm_circuit_breaker,
    logger,
    plugin_system_service,
    record_llm_latency,
    run_hooks,
)
from app.services.plugin_system_service import ExtensionPoint


async def plan_node(state: AgentState, config: RunnableConfig | None = None) -> dict:
    """
    Call the LLM with the current messages + tool schemas.
    """
    agent_config: AgentConfig = state["config"]
    model = state.get("selected_model", agent_config.model)
    messages = state.get("messages", [])
    iteration = state.get("iteration", 0)
    rag_context = state.get("rag_context", "")

    # Lifecycle Hook: before_prompt_build
    hook_ctx = await run_hooks("before_prompt_build", {
        "messages": messages,
        "model": model,
        "iteration": iteration,
        "rag_context": rag_context,
        "user_id": agent_config.user_id,
        "scene_code": state.get("scene_code", ""),
    })
    if hook_ctx:
        # Allow hooks to inject extra context or modify messages
        messages = hook_ctx.get("messages", messages)
        rag_context = hook_ctx.get("rag_context", rag_context)

    # Resolve model via LLM gateway (P2-9: complexity-aware routing)
    resolved = None
    try:
        from app.services.llm_helpers import resolve_model_config

        org_id = agent_config.org_id or "default"
        scene_code = state.get("scene_code", "")
        agent_code = state.get("agent_code", "")
        complexity = state.get("complexity", QueryComplexity.MODERATE)
        resolved = await resolve_model_config(org_id, scene_code, agent_code, complexity_tier=complexity.model_tier)
    except Exception:
        logger.debug("LLM gateway model config unavailable in plan_node, using default")

    # Convert to LC format
    lc_msgs = _messages_to_lc_format(messages)

    # ── Dynamic System Prompt Injection ──
    # Inject user_role and available_tools into the system prompt
    intent_summary = state.get("intent_summary", "")
    if iteration == 0:
        extra_lines = []
        user_role = agent_config.user_role
        if user_role:
            extra_lines.append(f"当前用户角色: {user_role}")

        tool_schemas = _get_tool_schemas(agent_config.user_role, intent_summary=intent_summary, scene_code=state.get("scene_code"))
        if complexity == QueryComplexity.SIMPLE:
            # SIMPLE: only show universal tools in system prompt
            tool_schemas = [s for s in tool_schemas if s["function"]["name"] in _ALWAYS_INCLUDE_TOOLS]
        if tool_schemas:
            tool_names = ", ".join(t["function"]["name"] for t in tool_schemas)
            extra_lines.append(f"可用工具: {tool_names}")

        if extra_lines:
            injection = "\n".join(extra_lines)
            injected = False
            for _i, m in enumerate(lc_msgs):
                if isinstance(m, SystemMessage):
                    m.content += f"\n\n{injection}"
                    injected = True
                    break
            if not injected:
                lc_msgs.insert(0, SystemMessage(content=injection))

        # Few-shot example injection — scene/intent-aware style demonstrations
        try:
            from app.core.prompts.few_shot_examples import get_few_shot_examples

            scene_code = state.get("scene_code", "")
            few_shot = get_few_shot_examples(scene_code, intent_summary)
            if few_shot:
                for m in lc_msgs:
                    if isinstance(m, SystemMessage):
                        m.content += f"\n\n{few_shot}"
                        break
        except Exception:
            pass  # Few-shot injection is optional, never block planning

    # P0-3: On re-planning iterations, inject reflection guidance into system prompt
    if iteration > 0:
        reflection_guidance = state.get("reflection_guidance", "")
        if reflection_guidance:
            guidance_injection = (
                f"\n\n[重要：反思修正指令]\n{reflection_guidance}\n"
                f"请根据以上指令调整你的回复策略。当前是第{iteration + 1}轮规划。"
            )
            injected_guidance = False
            for m in lc_msgs:
                if isinstance(m, SystemMessage):
                    m.content += guidance_injection
                    injected_guidance = True
                    break
            if not injected_guidance:
                lc_msgs.insert(0, SystemMessage(content=guidance_injection))

    # ── RAG Injection ──
    # If we have retrieved context, prepend it to the history or inject into system prompt
    if rag_context and iteration == 0:
        rag_disclaimer = (
            "【重要：文档来源区分】\n"
            "以下检索结果可能来自不同类型的文档，请注意区分：\n"
            "- [招标文件]: 客户/甲方发布的采购需求，其中提到的产品规格是客户要求，不代表我方产品\n"
            "- [投标文件]: 我方编写的投标响应文档\n"
            "- [产品资料]: 我方的产品说明、规格书等，代表我方实际能力\n"
            "- 无标签的内容请根据上下文自行判断来源\n"
            "回答时务必区分「客户要求」和「我方能力」，切勿将招标文件中的需求当作我方产品参数。\n"
        )
        rag_block = f"\n\n{rag_disclaimer}\n[检索到的参考知识]:\n{rag_context}"
        found_sys = False
        for _i, m in enumerate(lc_msgs):
            if isinstance(m, SystemMessage):
                m.content += rag_block
                found_sys = True
                break
        if not found_sys:
            lc_msgs.insert(0, SystemMessage(content=f"你可以参考以下背景知识来回答问题:{rag_block}"))

    # Decide whether to include tools
    complexity = state.get("complexity", QueryComplexity.MODERATE)

    # ── Task 1 & 2: LangChain Planning + Streaming ──
    # Use ChatOpenAI with streaming and bind_tools
    llm = _get_llm(agent_config, model=model, streaming=True, resolved_config=resolved)
    if complexity == QueryComplexity.SIMPLE:
        # SIMPLE queries: only bind lightweight universal tools (web_search, llm_task)
        # so LLM can still search the web for "推荐电影" etc., without loading 130+ business tools
        simple_schemas = [
            s for s in _get_tool_schemas(agent_config.user_role, scene_code=state.get("scene_code"))
            if s["function"]["name"] in _ALWAYS_INCLUDE_TOOLS
        ]
        if simple_schemas:
            llm = llm.bind_tools(simple_schemas, parallel_tool_calls=True)
    else:
        llm = llm.bind_tools(_get_tool_schemas(agent_config.user_role, intent_summary=intent_summary, scene_code=state.get("scene_code")), parallel_tool_calls=True)

    thinking_step = ThinkingStep(
        phase=AgentPhase.PLANNING.value,
        content=f"正在分析意图并规划执行路径... (轮次 {iteration + 1})",
    )

    # P1 Plugin: PRE_CHAT hook
    try:
        hook_ctx = await plugin_system_service.run_hooks(
            ExtensionPoint.PRE_CHAT,
            {"messages": lc_msgs, "model": model, "config": agent_config},
        )
        if "messages" in hook_ctx and isinstance(hook_ctx["messages"], list):
            lc_msgs = hook_ctx["messages"]
    except Exception as e:
        logger.debug(f"[PlanNode] PRE_CHAT hook error: {e}")

    # Call LLM via standard invoke (with automatic fallback to backup provider)
    # Circuit breaker check for LLM service
    if not llm_circuit_breaker.allow_request():
        return {
            "error": "LLM 服务断路器已打开，请稍后重试。",
            "current_phase": AgentPhase.ERROR,
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.PLANNING.value,
                    content="⚠️ LLM 服务暂时不可用（断路器保护），请稍后再试",
                )
            ],
        }

    # Retry up to 2 times on timeout/connection errors (proxy APIs can be slow)
    _llm_start = time.time()
    if complexity == QueryComplexity.SIMPLE:
        tool_schemas = [
            s for s in _get_tool_schemas(agent_config.user_role, scene_code=state.get("scene_code"))
            if s["function"]["name"] in _ALWAYS_INCLUDE_TOOLS
        ] or None
    else:
        tool_schemas = _get_tool_schemas(agent_config.user_role, intent_summary=state.get("intent_summary", ""), scene_code=state.get("scene_code"))
    last_error = None
    for attempt in range(3):
        try:
            ai_msg = await invoke_with_fallback(
                llm,
                lc_msgs,
                config=agent_config,
                model=model,
                streaming=True,
                tool_schemas=tool_schemas,
            )
            record_llm_latency(model=model or agent_config.model, duration_ms=(time.time() - _llm_start) * 1000)
            llm_circuit_breaker.record_success()
            break
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            is_retryable = any(kw in error_str for kw in ("timeout", "timed out", "connection", "connect"))
            if is_retryable and attempt < 2:
                logger.warning(f"[PlanNode] LLM call timeout (attempt {attempt + 1}/3), retrying...")
                await asyncio.sleep(1.0 * (attempt + 1))
                continue
            # Non-retryable error or final attempt — give up
            llm_circuit_breaker.record_failure()
            logger.error(f"[PlanNode] LLM call failed after {attempt + 1} attempts: {e}")
            return {
                "error": f"LLM 规划失败: {str(e)}",
                "current_phase": AgentPhase.ERROR,
                "thinking_steps": [
                    ThinkingStep(
                        phase=AgentPhase.PLANNING.value,
                        content=f"⚠️ LLM 调用异常: {str(e)}",
                    )
                ],
            }

    # Track usage (LangChain usually provides this in additional_kwargs or response_metadata)
    usage = ai_msg.response_metadata.get("token_usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)

    # Langfuse: log LLM generation
    _configurable = (config or {}).get("configurable", {}) if isinstance(config, dict) else {}
    trace_logger = _configurable.get("trace_logger")
    if trace_logger:
        with contextlib.suppress(Exception):
            trace_logger.log_generation(
                model=model or agent_config.model,
                input_messages=[{"role": "user", "content": str(lc_msgs[-1].content)[:500]}] if lc_msgs else [],
                output=str(ai_msg.content or "")[:1000],
                usage={"prompt_tokens": input_tokens, "completion_tokens": output_tokens},
            )

    # P1 Plugin: POST_CHAT hook
    try:
        await plugin_system_service.run_hooks(
            ExtensionPoint.POST_CHAT,
            {"ai_message": ai_msg, "input_tokens": input_tokens, "output_tokens": output_tokens},
        )
    except Exception as e:
        logger.debug(f"[PlanNode] POST_CHAT hook error: {e}")

    tool_calls_raw = ai_msg.tool_calls
    content = ai_msg.content or ""

    # ── Empty Response Recovery ──
    # When LLM returns empty content with no tool calls after tools have executed,
    # inject a synthesis prompt and retry once. This prevents the empty-response
    # loop where reflect detects empty → replans → empty again → loop until max_iter.
    completed_tools = state.get("completed_tool_calls", [])
    if not content.strip() and not tool_calls_raw and completed_tools and iteration > 0:
        logger.warning("[PlanNode] LLM returned empty response after tool execution, retrying with synthesis prompt")
        # Build a concise summary of tool results for the retry
        tool_summaries = []
        for tc in completed_tools[-5:]:
            t_name = tc.tool_name if hasattr(tc, "tool_name") else tc.get("tool_name", "")
            t_result = (tc.result if hasattr(tc, "result") else tc.get("result", ""))[:300]
            t_status = tc.status if hasattr(tc, "status") else tc.get("status", "")
            tool_summaries.append(f"- {t_name} ({t_status}): {t_result}")
        synthesis_msg = SystemMessage(
            content=(
                "你刚才调用了工具并获得了结果，但没有生成回复。"
                "请根据以下工具执行结果，直接用中文回答用户的问题。\n\n"
                "工具结果:\n" + "\n".join(tool_summaries)
            )
        )
        retry_msgs = lc_msgs + [synthesis_msg]
        try:
            retry_llm = _get_llm(agent_config, model=model, streaming=True, resolved_config=resolved)
            # Don't bind tools — we want a text response, not more tool calls
            ai_msg = await retry_llm.ainvoke(retry_msgs)
            content = ai_msg.content or ""
            tool_calls_raw = ai_msg.tool_calls
            if content.strip():
                logger.info("[PlanNode] Empty response recovery succeeded")
            else:
                # Still empty — build a fallback response from tool results
                logger.warning("[PlanNode] Retry still empty, constructing fallback from tool results")
                fallback_parts = ["以下是工具执行结果：\n"]
                for tc in completed_tools:
                    t_name = tc.tool_name if hasattr(tc, "tool_name") else tc.get("tool_name", "")
                    t_result = (tc.result if hasattr(tc, "result") else tc.get("result", ""))[:500]
                    fallback_parts.append(f"**{t_name}**: {t_result}")
                content = "\n\n".join(fallback_parts)
                from langchain_core.messages import AIMessage as _AIMessage

                ai_msg = _AIMessage(content=content)
                tool_calls_raw = []
        except Exception as e:
            logger.error(f"[PlanNode] Empty response recovery failed: {e}")
            # Fall through with original empty response — let reflect handle it

    # Build pending tool call records
    pending_tools: list[ToolCallRecord] = []
    if tool_calls_raw:
        for tc in tool_calls_raw:
            tc_name = tc.get("name", "unknown")
            tc_args = tc.get("args", {})
            tc_id = tc.get("id", "")

            # Gemini concatenation bug: split concatenated tool names into separate records
            if not get_tool(tc_name):
                extracted = _try_extract_tool_names(tc_name)
                if extracted:
                    logger.warning(
                        f"[PlanNode] Splitting concatenated tool name '{tc_name}' "
                        f"into {len(extracted)} tools: {extracted}"
                    )
                    for i, ename in enumerate(extracted):
                        pending_tools.append(
                            ToolCallRecord(
                                tool_name=ename,
                                tool_args=tc_args if i == 0 else {},
                                tool_call_id=f"{tc_id}_split{i}" if tc_id else "",
                            )
                        )
                    continue

            pending_tools.append(
                ToolCallRecord(
                    tool_name=tc_name,
                    tool_args=tc_args,
                    tool_call_id=tc_id,
                )
            )

    # Construct the AIMessage to append to history
    # LangChain's ai_msg already is a BaseMessage
    result = {
        "messages": [ai_msg],
        "current_phase": AgentPhase.EXECUTING if pending_tools else AgentPhase.REFLECTING,
        "plan": content or "(执行工具调用)",
        "requires_tools": bool(pending_tools),
        "pending_tool_calls": pending_tools,
        "thinking_steps": [thinking_step],
        "total_input_tokens": state.get("total_input_tokens", 0) + input_tokens,
        "total_output_tokens": state.get("total_output_tokens", 0) + output_tokens,
    }

    if pending_tools:
        tool_names = ", ".join(t.tool_name for t in pending_tools)
        exec_step = ThinkingStep(
            phase=AgentPhase.PLANNING.value,
            content=f"计划调用工具: {tool_names}",
        )
        result["thinking_steps"] = [thinking_step, exec_step]
        # Langfuse: log tool plans
        if trace_logger:
            for t in pending_tools:
                with contextlib.suppress(Exception):
                    trace_logger.log_tool_plan(t.tool_name, t.tool_args)

    return result
