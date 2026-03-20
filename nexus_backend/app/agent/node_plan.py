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
    _format_validation_error,
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


async def _plan_with_self_consistency(
    lc_msgs: list,
    config: "AgentConfig",
    model: str | None,
    tool_schemas: list | None,
    resolved_config: dict | None = None,
    n: int = 3,
):
    """CRITICAL 查询多次采样 + 工具组合投票，选最一致的方案。

    使用 temperature=0.7 多次调用，提取每次的 tool_calls 列表，
    用 Counter 投票选工具组合一致性最高的方案。
    """
    from collections import Counter
    from langchain_openai import ChatOpenAI

    samples = []
    for i in range(n):
        try:
            # 直接创建 LLM 实例，覆盖 temperature 为 0.7
            sample_llm = ChatOpenAI(
                model=(resolved_config or {}).get("model") or model or config.model,
                api_key=(resolved_config or {}).get("api_key") or config.api_key,
                base_url=(resolved_config or {}).get("base_url") or config.base_url,
                temperature=0.7,
                streaming=False,
                timeout=30.0,
            )
            if tool_schemas:
                sample_llm = sample_llm.bind_tools(tool_schemas, parallel_tool_calls=True)
            result = await asyncio.wait_for(
                sample_llm.ainvoke(lc_msgs),
                timeout=30,
            )
            samples.append(result)
        except Exception as e:
            logger.debug(f"[SelfConsistency] Sample {i+1}/{n} failed: {e}")

    if not samples:
        return None  # 全部失败，退回单次调用

    # 按工具组合签名投票
    def _tool_signature(msg) -> str:
        calls = getattr(msg, "tool_calls", None) or []
        names = sorted(tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "") for tc in calls)
        return "|".join(names) if names else "__no_tools__"

    sigs = [_tool_signature(s) for s in samples]
    counter = Counter(sigs)
    best_sig, _count = counter.most_common(1)[0]

    # 选该签名的第一个样本
    for s, sig in zip(samples, sigs):
        if sig == best_sig:
            logger.info(f"[SelfConsistency] Selected tool combination: {best_sig} (votes: {_count}/{n})")
            return s

    return samples[0]


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

    # Resolve model via pre-resolved configs (Step 2: centralized resolution)
    resolved = None
    complexity = state.get("complexity", QueryComplexity.MODERATE)

    # Auto-detect tier when router didn't explicitly set complexity (default MODERATE)
    if complexity == QueryComplexity.MODERATE and "complexity" not in state:
        try:
            from app.services.llm_helpers import auto_detect_tier
            tool_schemas_for_tier = _get_tool_schemas(agent_config.user_role, scene_code=state.get("scene_code"))
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
            logger.debug("Auto-detected tier=%s → complexity=%s", detected_tier, complexity.value)
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
            resolved = await resolve_model_config(org_id, scene_code, agent_code, complexity_tier=complexity.model_tier)
        except Exception:
            logger.debug("LLM gateway model config unavailable in plan_node, using default")

    # Convert to LC format
    lc_msgs = _messages_to_lc_format(messages)

    # ── Item 48: Prompt Compression ──
    # Compress conversation history when it exceeds thresholds to reduce token usage.
    # Applied before system prompt injection so the compression operates on raw history.
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
        logger.debug(f"[PlanNode] Prompt compression failed, using full history: {e}")

    # ── Dynamic System Prompt Injection ──
    # Inject user_role and available_tools into the system prompt
    intent_summary = state.get("intent_summary", "")
    if iteration == 0:
        extra_lines = []
        user_role = agent_config.user_role
        if user_role:
            extra_lines.append(f"当前用户角色: {user_role}")

        tool_schemas = _get_tool_schemas(agent_config.user_role, intent_summary=intent_summary, scene_code=state.get("scene_code"), intent_domains=state.get("intent_domains"))
        if complexity == QueryComplexity.SIMPLE:
            # SIMPLE: only show universal tools in system prompt
            tool_schemas = [s for s in tool_schemas if s["function"]["name"] in _ALWAYS_INCLUDE_TOOLS]
        if tool_schemas:
            tool_names = ", ".join(t["function"]["name"] for t in tool_schemas)
            extra_lines.append(f"可用工具: {tool_names}")

        if extra_lines:
            injection = "\n".join(extra_lines)
            # 独立 SystemMessage，避免 Prompt Bloat（不再 append 到主 system prompt）
            lc_msgs.insert(1 if lc_msgs and isinstance(lc_msgs[0], SystemMessage) else 0,
                           SystemMessage(content=f"[角色与工具]\n{injection}"))

        # ── CoT 推理框架: 仅 COMPLEX/CRITICAL 注入，降低简单查询延迟 ──
        if complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL):
            cot_prompt = (
                "[推理框架]\n"
                "在调用任何工具之前，请先在内心完成以下推理步骤：\n"
                "1. 意图解析：用户真正想要什么？有无隐含需求？\n"
                "2. 信息缺口：回答这个问题还缺哪些数据？\n"
                "3. 工具规划：需要调用哪些工具、以什么顺序？\n"
                "4. 风险评估：操作是否不可逆？是否需要用户确认？\n"
                "5. 验收标准：怎样的回复才算完整解决了用户问题？\n"
                "请直接执行，无需在回复中展示推理过程。"
            )
            insert_pos = 2 if len(lc_msgs) > 1 else len(lc_msgs)
            lc_msgs.insert(insert_pos, SystemMessage(content=cot_prompt))

        # Few-shot example injection — scene/intent-aware style demonstrations
        try:
            from app.core.prompts.few_shot_examples import get_few_shot_examples

            scene_code = state.get("scene_code", "")
            few_shot = get_few_shot_examples(scene_code, intent_summary)
            if few_shot:
                # 独立 SystemMessage，与主 system prompt 分离
                lc_msgs.insert(2 if len(lc_msgs) > 1 else len(lc_msgs),
                               SystemMessage(content=f"[参考示例]\n{few_shot}"))
        except Exception:
            pass  # Few-shot injection is optional, never block planning

    # P0-3: On re-planning iterations, inject reflection guidance into system prompt
    if iteration > 0:
        reflection_guidance = state.get("reflection_guidance", "")
        if reflection_guidance:
            guidance_content = (
                f"[重要：反思修正指令]\n{reflection_guidance}\n"
                f"请根据以上指令调整你的回复策略。当前是第{iteration + 1}轮规划。"
            )
            # 独立 SystemMessage，紧接在主 system prompt 之后
            lc_msgs.insert(1 if lc_msgs and isinstance(lc_msgs[0], SystemMessage) else 0,
                           SystemMessage(content=guidance_content))

        # Inject current task board state so AI doesn't drift across iterations
        try:
            from app.core.database import supabase as _db
            _session_id = agent_config.session_id or "default"
            _tasks_res = (
                await _db.table("agent_tasks")
                .select("title, status, context_summary")
                .eq("user_id", agent_config.user_id)
                .eq("conversation_id", _session_id)
                .order("sort_order")
                .order("created_at")
                .limit(15)
                .execute()
            )
            _tasks = _tasks_res.data or []
            if _tasks:
                _icons = {"pending": "⬜", "in_progress": "🔄", "done": "✅", "blocked": "🚫"}
                _lines = [f"[当前任务板 — 第{iteration + 1}轮规划，请据此决定下一步]"]
                for _t in _tasks:
                    _icon = _icons.get(_t["status"], "❓")
                    _line = f"{_icon} {_t['title']}"
                    if _t.get("context_summary"):
                        _line += f"（{_t['context_summary'][:60]}）"
                    _lines.append(_line)
                lc_msgs.insert(
                    1 if lc_msgs and isinstance(lc_msgs[0], SystemMessage) else 0,
                    SystemMessage(content="\n".join(_lines)),
                )
        except Exception:
            pass  # Task board injection is optional

    # P0: Inject compacted context summary if agent previously compressed context
    compacted_summary = state.get("context_compacted_summary", "")
    if compacted_summary:
        lc_msgs.insert(
            1 if lc_msgs and isinstance(lc_msgs[0], SystemMessage) else 0,
            SystemMessage(content=f"[上下文摘要 — 之前的对话和工具结果已压缩]\n{compacted_summary}"),
        )

    # ── Context Engine 集成：统一上下文组装 ──
    # 替代硬编码 RAG 注入，通过 ContextEngine 按优先级和 token 预算获取上下文
    if iteration == 0:
        try:
            from app.agent.context_engine import context_engine

            engine_ctx = await context_engine.build_context(
                user_id=agent_config.user_id,
                org_id=agent_config.org_id,
                query=state.get("intent_summary") or (messages[-1].content if messages else ""),
                session_id=agent_config.session_id,
            )
            if engine_ctx:
                lc_msgs.insert(
                    1 if lc_msgs and isinstance(lc_msgs[0], SystemMessage) else 0,
                    SystemMessage(content=f"[上下文引擎检索结果]\n{engine_ctx}"),
                )
        except Exception as e:
            logger.debug(f"[PlanNode] ContextEngine failed, falling back to raw RAG: {e}")
            engine_ctx = ""

        # RAG 上下文（来自 rag_inject 节点的预检索结果）作为补充
        if rag_context:
            rag_disclaimer = (
                "【重要：文档来源区分】\n"
                "以下检索结果可能来自不同类型的文档，请注意区分：\n"
                "- [招标文件]: 客户/甲方发布的采购需求，其中提到的产品规格是客户要求，不代表我方产品\n"
                "- [投标文件]: 我方编写的投标响应文档\n"
                "- [产品资料]: 我方的产品说明、规格书等，代表我方实际能力\n"
                "- 无标签的内容请根据上下文自行判断来源\n"
                "回答时务必区分「客户要求」和「我方能力」，切勿将招标文件中的需求当作我方产品参数。\n"
            )
            rag_block = f"{rag_disclaimer}\n[检索到的参考知识]\n{rag_context}"
            lc_msgs.insert(
                1 if lc_msgs and isinstance(lc_msgs[0], SystemMessage) else 0,
                SystemMessage(content=rag_block),
            )

    # P1: Task decomposition — inject step-focused plan for active step
    _task_steps = state.get("_task_steps", [])
    _active_idx = state.get("_active_step_index", 0)
    _decomp_done = state.get("_task_decomposition_done", False)

    if _decomp_done and _task_steps and _active_idx < len(_task_steps):
        current_step = _task_steps[_active_idx]
        criteria = current_step.get('acceptance_criteria', '')
        criteria_line = f"\n验收标准: {criteria}\n请确保满足验收标准后再结束此步骤。" if criteria else ""
        step_instruction = (
            f"[当前执行步骤 {_active_idx + 1}/{len(_task_steps)}]\n"
            f"标题: {current_step.get('title', '')}\n"
            f"描述: {current_step.get('description', '')}"
            f"{criteria_line}\n"
            f"请专注完成此步骤，不要跳到其他步骤。"
        )
        lc_msgs.insert(
            1 if lc_msgs and isinstance(lc_msgs[0], SystemMessage) else 0,
            SystemMessage(content=step_instruction),
        )

    # P1: On first iteration for COMPLEX+ queries, request task decomposition
    if (
        iteration == 0
        and not _decomp_done
        and complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL)
    ):
        decomp_hint = (
            "\n\n[任务分解指令] 如果此任务涉及多个独立步骤（如先查询再分析再生成），"
            "请在回复开头用以下JSON格式输出任务分解（用```json包裹）：\n"
            '```json\n{"task_steps": [{"title": "步骤标题", "description": "步骤描述", '
            '"acceptance_criteria": "该步骤完成的客观判定条件，如：成功获取到数据/生成了包含X的报告"}]}\n```\n'
            "如果任务简单无需分解，直接正常回复即可。"
        )
        # Append to last user message context
        if lc_msgs and hasattr(lc_msgs[-1], "content"):
            from langchain_core.messages import HumanMessage as _HM
            if isinstance(lc_msgs[-1], _HM):
                lc_msgs[-1] = _HM(content=lc_msgs[-1].content + decomp_hint)

    # Decide whether to include tools
    complexity = state.get("complexity", QueryComplexity.MODERATE)

    # ── Task 1 & 2: LangChain Planning + Streaming ──
    # Use ChatOpenAI with streaming and bind_tools
    llm = _get_llm(agent_config, model=model, streaming=True, resolved_config=resolved)

    # Determine if any pending tools are irreversible (for tool_choice enforcement)
    _has_irreversible_context = False
    if iteration > 0 and state.get("completed_tool_calls"):
        # On re-planning after blocked irreversible tools, force tool usage
        _has_irreversible_context = any(
            getattr(tc, "status", None) == "blocked" for tc in state.get("completed_tool_calls", [])
        )

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
        bind_kwargs = {"parallel_tool_calls": True}
        # For re-planning after irreversible tool confirmation, force tool usage
        # to prevent the LLM from hallucinating a response instead of calling tools
        if _has_irreversible_context and agent_config.system_confirmed:
            bind_kwargs["tool_choice"] = "required"
        llm = llm.bind_tools(
            _get_tool_schemas(agent_config.user_role, intent_summary=intent_summary, scene_code=state.get("scene_code"), intent_domains=state.get("intent_domains")),
            **bind_kwargs,
        )

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
        tool_schemas = _get_tool_schemas(agent_config.user_role, intent_summary=state.get("intent_summary", ""), scene_code=state.get("scene_code"), intent_domains=state.get("intent_domains"))
    last_error = None
    _sc_succeeded = False

    # ── CRITICAL Self-Consistency: 多次采样投票（仅首轮） ──
    if complexity == QueryComplexity.CRITICAL and iteration == 0:
        sc_result = await _plan_with_self_consistency(
            lc_msgs, agent_config, model, tool_schemas, resolved_config=resolved,
        )
        if sc_result is not None:
            ai_msg = sc_result
            record_llm_latency(model=model or agent_config.model, duration_ms=(time.time() - _llm_start) * 1000)
            llm_circuit_breaker.record_success()
            _sc_succeeded = True
        else:
            logger.warning("[PlanNode] Self-Consistency failed, falling back to single invoke")

    if not _sc_succeeded:
        for attempt in range(3):
            try:
                ai_msg = await invoke_with_fallback(
                    llm,
                    lc_msgs,
                    config=agent_config,
                    model=model,
                    streaming=True,
                    tool_schemas=tool_schemas,
                    complexity_tier=complexity.model_tier,
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

    # Diagnostic: log LLM response details for debugging empty/short responses
    finish_reason = ai_msg.response_metadata.get("finish_reason", "unknown")
    # Detect API provider silently downgrading the model
    actual_api_model = ai_msg.response_metadata.get("model_name") or ai_msg.response_metadata.get("model", "")
    content_len = len(ai_msg.content or "")
    tool_call_count = len(ai_msg.tool_calls or [])
    requested_model = model or agent_config.model
    logger.info(
        "[PlanNode] LLM response: requested=%s actual=%s finish=%s content_len=%d "
        "tool_calls=%d in_tok=%d out_tok=%d",
        requested_model, actual_api_model or "?", finish_reason, content_len,
        tool_call_count, input_tokens, output_tokens,
    )
    if actual_api_model and actual_api_model != requested_model and requested_model not in actual_api_model:
        logger.warning(
            "[PlanNode] MODEL MISMATCH: requested '%s' but API returned '%s' — provider may have downgraded",
            requested_model, actual_api_model,
        )

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

    # ── Short/Useless Response Recovery (First Iteration) ──
    # When a COMPLEX/CRITICAL query gets a very short response with NO tool calls
    # on the first iteration, the LLM likely failed silently (wrong model, context
    # overflow, etc.). Retry with fallback LLM to avoid returning garbage.
    if (
        iteration == 0
        and not tool_calls_raw
        and len(content.strip()) < 100
        and complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL)
    ):
        logger.warning(
            f"[PlanNode] Short response ({len(content.strip())} chars) with no tool calls "
            f"for {complexity.value} query — retrying with fallback LLM"
        )
        try:
            from app.agent.node_helpers import _get_fallback_llm
            fallback_llm = _get_fallback_llm(agent_config, model=model, streaming=True)
            if fallback_llm:
                if tool_schemas:
                    fallback_llm = fallback_llm.bind_tools(tool_schemas, parallel_tool_calls=True)
                ai_msg = await fallback_llm.ainvoke(lc_msgs)
                content = ai_msg.content or ""
                tool_calls_raw = ai_msg.tool_calls
                if tool_calls_raw or len(content.strip()) >= 100:
                    logger.info("[PlanNode] Short response recovery succeeded via fallback LLM")
                else:
                    logger.warning("[PlanNode] Fallback LLM also returned short response")
            else:
                logger.info("[PlanNode] No fallback LLM available for short response recovery")
        except Exception as e:
            logger.error(f"[PlanNode] Short response recovery failed: {e}")

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

    # Build pending tool call records with pre-execution schema validation
    pending_tools: list[ToolCallRecord] = []
    validation_errors: list[str] = []
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
                        if i == 0:
                            # First tool gets the original args
                            pending_tools.append(
                                ToolCallRecord(
                                    tool_name=ename,
                                    tool_args=tc_args,
                                    tool_call_id=f"{tc_id}_split{i}" if tc_id else "",
                                )
                            )
                        else:
                            # Subsequent tools: try to extract matching args from schema
                            split_tool = get_tool(ename)
                            if split_tool and hasattr(split_tool, "parameters") and split_tool.parameters:
                                required = set(split_tool.parameters.get("required", []))
                                all_props = set(split_tool.parameters.get("properties", {}).keys())
                                split_args = {k: v for k, v in tc_args.items() if k in all_props}
                                if required and required.issubset(split_args.keys()):
                                    pending_tools.append(
                                        ToolCallRecord(
                                            tool_name=ename,
                                            tool_args=split_args,
                                            tool_call_id=f"{tc_id}_split{i}" if tc_id else "",
                                        )
                                    )
                                else:
                                    logger.warning(
                                        "[PlanNode] Skipping split tool '%s': "
                                        "required args %s not found in available %s",
                                        ename, required, set(tc_args.keys()),
                                    )
                            else:
                                logger.warning(
                                    "[PlanNode] Skipping split tool '%s': tool not found or no schema",
                                    ename,
                                )
                    continue

            # Pre-execution schema validation: catch bad args before execute_node
            tool_obj = get_tool(tc_name)
            if tool_obj and tool_obj.parameters and tc_args:
                try:
                    import jsonschema
                    jsonschema.validate(instance=tc_args, schema=tool_obj.parameters)
                except Exception as ve:
                    error_msg = _format_validation_error(tc_name, ve, tool_obj.parameters)
                    validation_errors.append(error_msg)
                    logger.warning(f"[PlanNode] Pre-exec validation failed for {tc_name}: {ve}")
                    # Still add to pending — execute_node will catch it too,
                    # but we collect errors to give LLM a chance to self-correct
                    pending_tools.append(
                        ToolCallRecord(
                            tool_name=tc_name,
                            tool_args=tc_args,
                            tool_call_id=tc_id,
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

    # If validation errors were found, inject guidance into next iteration
    # so LLM can self-correct parameters before execution
    if validation_errors and iteration < (agent_config.max_iterations - 1):
        error_feedback = "\n\n".join(validation_errors)
        logger.info(f"[PlanNode] {len(validation_errors)} tool arg validation errors, requesting LLM correction")
        # Clear invalid tools and return to planning with error feedback
        from langchain_core.messages import AIMessage as _AIMessage

        correction_msg = _AIMessage(
            content=f"[参数校验错误] 以下工具调用参数不符合要求，请修正后重试:\n\n{error_feedback}"
        )
        return {
            "messages": [correction_msg],
            "current_phase": AgentPhase.PLANNING,
            "plan": content or "(参数校验失败，需修正)",
            "requires_tools": False,
            "pending_tool_calls": [],
            "thinking_steps": [
                thinking_step,
                ThinkingStep(
                    phase=AgentPhase.PLANNING.value,
                    content=f"工具参数校验失败 ({len(validation_errors)} 个错误)，请求 LLM 修正参数",
                ),
            ],
            "reflection_guidance": f"工具参数校验失败，请修正以下问题:\n{error_feedback}",
            "needs_replanning": True,
            "iteration": iteration + 1,
            "total_input_tokens": state.get("total_input_tokens", 0) + input_tokens,
            "total_output_tokens": state.get("total_output_tokens", 0) + output_tokens,
        }

    # P1: Parse task decomposition from LLM response
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
        json_match = _re.search(r"```json\s*(\{.*?\"task_steps\".*?\})\s*```", content, _re.DOTALL)
        if json_match:
            try:
                parsed = _json.loads(json_match.group(1))
                steps = parsed.get("task_steps", [])
                if isinstance(steps, list) and 2 <= len(steps) <= 8:
                    _new_task_steps = steps
                    # Remove the JSON block from content so it doesn't appear in the response
                    content = content[:json_match.start()] + content[json_match.end():]
                    content = content.strip()
                    logger.info(f"[PlanNode] Task decomposed into {len(steps)} steps: {[s.get('title') for s in steps]}")
            except (_json.JSONDecodeError, KeyError):
                pass  # Not valid JSON, ignore

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

    # P1: Store task decomposition in state
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
        # Advance to next step only if not a step retry (goal-driven acceptance check)
        reflection_guidance = state.get("reflection_guidance", "")
        is_step_retry = "未完成" in reflection_guidance and f"步骤 {_active_idx + 1}" in reflection_guidance
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
        if trace_logger:
            for t in pending_tools:
                with contextlib.suppress(Exception):
                    trace_logger.log_tool_plan(t.tool_name, t.tool_args)

    return result
