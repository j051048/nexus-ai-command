"""System prompt assembly: [D] dynamic injection, [E] re-planning, [F] slot filling & context engine."""

from langchain_core.messages import SystemMessage

from app.agent.node_helpers import (
    _ALWAYS_INCLUDE_TOOLS,
    AgentConfig,
    QueryComplexity,
    _get_tool_schemas,
    logger,
)


async def inject_system_prompts(
    lc_msgs: list,
    *,
    state: dict,
    agent_config: AgentConfig,
    complexity: QueryComplexity,
    intent_summary: str,
    iteration: int,
    rag_context: str,
) -> list:
    """Inject all system-prompt blocks into *lc_msgs* (mutates and returns it).

    Covers segments [D], [E], [F] from the original plan_node.
    """
    await _resolve_runtime_prompt_artifact(state, agent_config)
    # ── [D] Dynamic System Prompt Injection (first iteration only) ──
    if iteration == 0:
        _inject_role_and_tools(lc_msgs, agent_config, complexity, intent_summary, state)
        _inject_cot_framework(lc_msgs, complexity)
        await _inject_error_learning(
            lc_msgs, agent_config, state, complexity, intent_summary
        )
        await _inject_few_shot(lc_msgs, agent_config, state, intent_summary)
        _inject_role_few_shot(lc_msgs, agent_config)

    # ── [E] Re-planning injection ──
    if iteration > 0:
        _inject_reflection_guidance(lc_msgs, state, iteration)
        await _inject_task_board(lc_msgs, agent_config, state, iteration)

    # Compacted context summary
    _inject_compacted_summary(lc_msgs, state)

    # ── [F] Slot filling & Context Engine ──
    _inject_slot_context(lc_msgs, state)
    if iteration == 0:
        await _inject_context_engine(lc_msgs, state, agent_config, complexity)
        _inject_rag_context(lc_msgs, rag_context)

    # Task decomposition hints
    _inject_task_decomposition(lc_msgs, state, complexity, iteration)

    lc_msgs = _compile_global_context(lc_msgs, state, agent_config, complexity)

    _attach_prompt_snapshot(lc_msgs, state, agent_config, complexity)

    return lc_msgs


def _compile_global_context(lc_msgs, state, agent_config, complexity):
    """Apply one global budget after every prompt/context injector has run."""
    try:
        from app.agent.context_compiler import (
            ContextCompilePolicy,
            context_compiler,
        )

        resolved = agent_config.resolved_configs or {}
        tier_key = (
            complexity.model_tier if hasattr(complexity, "model_tier") else "balanced"
        )
        context_window = int(
            (resolved.get(tier_key) or {}).get("context_window") or 32_000
        )
        compiled, report = context_compiler.compile(
            lc_msgs,
            policy=ContextCompilePolicy(max_input_tokens=context_window),
            ledger=state.get("context_ledger") or {},
        )
        state["context_compile_report"] = report.to_dict()
        state["evidence_contract"] = {
            "evidence_ids": report.evidence_ids,
            "context_fingerprint": report.fingerprint,
            "requires_citations": bool(report.evidence_ids),
        }
        return compiled
    except Exception as e:
        logger.warning("[PromptBuilder] global context compilation skipped: %s", e)
        return lc_msgs


# ---------------------------------------------------------------------------
# [D] helpers
# ---------------------------------------------------------------------------


def _inject_role_and_tools(lc_msgs, agent_config, complexity, intent_summary, state):
    extra_lines = []
    if state.get("prompt_artifact_header"):
        extra_lines.append(state["prompt_artifact_header"])
    try:
        from app.services.prompt_registry import prompt_registry

        if not state.get("prompt_artifact_header"):
            registry_header = prompt_registry.build_runtime_header(
                getattr(agent_config, "agent_code", None)
            )
            extra_lines.append(registry_header)
            state["prompt_version"] = prompt_registry.resolve_prompt_version(
                getattr(agent_config, "agent_code", None)
            )
    except Exception as e:
        logger.debug("[PromptBuilder] Prompt registry injection skipped: %s", e)

    user_role = agent_config.user_role
    if user_role:
        extra_lines.append(f"当前用户角色: {user_role}")

    tool_schemas = _get_tool_schemas(
        agent_config.user_role,
        intent_summary=intent_summary,
        scene_code=state.get("scene_code"),
        intent_domains=state.get("intent_domains"),
    )
    if complexity == QueryComplexity.SIMPLE:
        tool_schemas = [
            s for s in tool_schemas if s["function"]["name"] in _ALWAYS_INCLUDE_TOOLS
        ]
    if tool_schemas:
        tool_names = ", ".join(t["function"]["name"] for t in tool_schemas)
        extra_lines.append(f"可用工具: {tool_names}")

    if extra_lines:
        injection = "\n".join(extra_lines)
        lc_msgs.insert(
            1 if lc_msgs and isinstance(lc_msgs[0], SystemMessage) else 0,
            SystemMessage(content=f"[角色与工具]\n{injection}"),
        )


async def _resolve_runtime_prompt_artifact(state, agent_config):
    try:
        from app.services.prompt_artifact_service import prompt_artifact_resolver

        agent_code = getattr(agent_config, "agent_code", None) or getattr(
            agent_config, "agent_name", None
        )
        artifact = await prompt_artifact_resolver.resolve(
            agent_code=agent_code,
            organization_id=getattr(agent_config, "org_id", None),
        )
        state["prompt_version"] = artifact.version
        state["prompt_artifact"] = {
            "agent_code": artifact.agent_code,
            "version": artifact.version,
            "content_hash": artifact.content_hash,
            "source": artifact.source,
            "risk_tier": artifact.risk_tier,
        }
        state["prompt_artifact_header"] = prompt_artifact_resolver.runtime_header(
            artifact
        )
    except Exception as e:
        logger.debug("[PromptBuilder] Prompt artifact resolution skipped: %s", e)


def _inject_cot_framework(lc_msgs, complexity):
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


async def _inject_error_learning(
    lc_msgs, agent_config, state, complexity, intent_summary
):
    try:
        from app.agent.learning_system import learning_system

        tool_schemas = _get_tool_schemas(
            agent_config.user_role,
            intent_summary=intent_summary,
            scene_code=state.get("scene_code"),
            intent_domains=state.get("intent_domains"),
        )
        if complexity == QueryComplexity.SIMPLE:
            tool_schemas = [
                s
                for s in tool_schemas
                if s["function"]["name"] in _ALWAYS_INCLUDE_TOOLS
            ]

        _org_id = agent_config.org_id
        _tool_names_list = (
            [t["function"]["name"] for t in tool_schemas] if tool_schemas else []
        )
        _warnings: list[str] = []
        for _tn in _tool_names_list:
            _patterns = await learning_system.get_learned_patterns(_tn, _org_id)
            if _patterns:
                top = _patterns[0]
                _warnings.append(
                    f"- {_tn}: 历史常见错误「{top.get('error_pattern', '')[:80]}」(出现{top.get('frequency', 0)}次)"
                )
        if _warnings:
            _warn_text = (
                "[历史失败教训]\n以下工具曾出现过错误，请注意规避：\n"
                + "\n".join(_warnings[:5])
            )
            lc_msgs.insert(
                2 if len(lc_msgs) > 1 else len(lc_msgs),
                SystemMessage(content=_warn_text),
            )
    except Exception as e:
        logger.debug("[PromptBuilder] Learning system injection skipped: %s", e)


async def _inject_few_shot(lc_msgs, agent_config, state, intent_summary):
    try:
        from app.core.prompts.few_shot_examples import get_few_shot_examples

        scene_code = state.get("scene_code", "")
        few_shot = None

        # Try dynamic few-shot: retrieve golden_example from conversation_memories
        try:
            from app.core.database import supabase as _mem_db

            if _mem_db and agent_config.user_id:
                golden_res = (
                    await _mem_db.table("conversation_memories")
                    .select("value")
                    .eq("user_id", agent_config.user_id)
                    .eq("category", "golden_example")
                    .is_("superseded_by", "null")
                    .order("importance", desc=True)
                    .limit(2)
                    .execute()
                )
                if golden_res.data:
                    from app.services.conversation_memory.storage import (
                        decrypt_memory_value,
                    )

                    ex_parts = [
                        decrypt_memory_value(r["value"]) for r in golden_res.data
                    ]
                    few_shot = "【历史优秀对话参考】\n" + "\n---\n".join(ex_parts)
        except Exception as e:
            logger.debug(
                "[PromptBuilder] Dynamic few-shot lookup failed, using static: %s", e
            )

        # Fallback to static scene/intent-aware examples
        if not few_shot:
            few_shot = get_few_shot_examples(scene_code, intent_summary)

        if few_shot:
            lc_msgs.insert(
                2 if len(lc_msgs) > 1 else len(lc_msgs),
                SystemMessage(content=f"[参考示例]\n{few_shot}"),
            )
    except Exception as e:
        logger.debug("[PromptBuilder] Few-shot injection skipped: %s", e)


def _inject_role_few_shot(lc_msgs, agent_config):
    try:
        from app.agent.roles.registry import get_role_config_sync

        _agent_code = getattr(agent_config, "agent_code", None) or "director_agent"
        _role = get_role_config_sync(_agent_code)
        if _role.few_shot_examples:
            _examples = []
            for ex in _role.few_shot_examples[:3]:
                _examples.append(f"用户: {ex['user']}\n助手: {ex['assistant']}")
            _ex_text = "\n---\n".join(_examples)
            lc_msgs.insert(
                2 if len(lc_msgs) > 1 else len(lc_msgs),
                SystemMessage(content=f"[角色参考示例]\n{_ex_text}"),
            )
    except Exception as e:
        logger.debug("[PromptBuilder] Role few-shot injection skipped: %s", e)


# ---------------------------------------------------------------------------
# [E] helpers
# ---------------------------------------------------------------------------


def _inject_reflection_guidance(lc_msgs, state, iteration):
    reflection_guidance = state.get("reflection_guidance", "")
    if reflection_guidance:
        guidance_content = (
            f"[重要：反思修正指令]\n{reflection_guidance}\n"
            f"请根据以上指令调整你的回复策略。当前是第{iteration + 1}轮规划。"
        )
        lc_msgs.insert(
            1 if lc_msgs and isinstance(lc_msgs[0], SystemMessage) else 0,
            SystemMessage(content=guidance_content),
        )


async def _inject_task_board(lc_msgs, agent_config, state, iteration):
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
            _icons = {
                "pending": "⬜",
                "in_progress": "🔄",
                "done": "✅",
                "blocked": "🚫",
            }
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
    except Exception as e:
        logger.debug("[PromptBuilder] Task board injection skipped: %s", e)


def _inject_compacted_summary(lc_msgs, state):
    compacted_summary = state.get("context_compacted_summary", "")
    if compacted_summary:
        lc_msgs.insert(
            1 if lc_msgs and isinstance(lc_msgs[0], SystemMessage) else 0,
            SystemMessage(
                content=f"[上下文摘要 — 之前的对话和工具结果已压缩]\n{compacted_summary}"
            ),
        )


# ---------------------------------------------------------------------------
# [F] helpers
# ---------------------------------------------------------------------------


def _inject_slot_context(lc_msgs, state):
    slot_ctx = state.get("slot_context")
    if slot_ctx:
        filled = slot_ctx.get("filled_slots", {})
        missing = slot_ctx.get("missing_slots", [])
        filled_str = (
            ", ".join(f"{k}={v}" for k, v in filled.items()) if filled else "无"
        )
        missing_str = ", ".join(missing)
        hint = (
            f"[槽位填充提示] 用户正在补充「{slot_ctx['tool_name']}」工具的参数。\n"
            f"已有参数: {filled_str}\n"
            f"缺失参数: {missing_str}\n"
            f"请根据用户最新回复提取缺失参数值，调用该工具时确保包含所有参数。"
        )
        lc_msgs.insert(
            1 if lc_msgs and isinstance(lc_msgs[0], SystemMessage) else 0,
            SystemMessage(content=hint),
        )


async def _inject_context_engine(lc_msgs, state, agent_config, complexity):
    try:
        from app.agent.context_engine import context_engine
        from app.agent.context_ledger import ContextLedger

        # Dynamic budget: adjust based on selected model's context window
        _resolved = agent_config.resolved_configs or {}
        _tier_key = (
            complexity.model_tier if hasattr(complexity, "model_tier") else "balanced"
        )
        _ctx_window = (_resolved.get(_tier_key) or {}).get("context_window")
        ledger = ContextLedger(request_id=state.get("trace_id") or state.get("run_id"))

        messages = state.get("messages", [])
        engine_ctx = await context_engine.build_context(
            user_id=agent_config.user_id,
            org_id=agent_config.org_id,
            query=state.get("intent_summary")
            or (messages[-1].content if messages else ""),
            context_window=_ctx_window,
            context_ledger=ledger,
            session_id=agent_config.session_id,
            user_role=agent_config.user_role,
        )
        state["context_ledger"] = ledger.to_dict()
        if engine_ctx:
            lc_msgs.insert(
                1 if lc_msgs and isinstance(lc_msgs[0], SystemMessage) else 0,
                SystemMessage(content=f"[上下文引擎检索结果]\n{engine_ctx}"),
            )
    except Exception as e:
        logger.error(f"[PlanNode] ContextEngine failed, falling back to raw RAG: {e}")


def _inject_rag_context(lc_msgs, rag_context):
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


def _inject_task_decomposition(lc_msgs, state, complexity, iteration):
    """Inject task-step focus and decomposition request into messages."""
    _task_steps = state.get("_task_steps", [])
    _active_idx = state.get("_active_step_index", 0)
    _decomp_done = state.get("_task_decomposition_done", False)

    if _decomp_done and _task_steps and _active_idx < len(_task_steps):
        current_step = _task_steps[_active_idx]
        criteria = current_step.get("acceptance_criteria", "")
        criteria_line = (
            f"\n验收标准: {criteria}\n请确保满足验收标准后再结束此步骤。"
            if criteria
            else ""
        )
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

    # On first iteration for COMPLEX+ queries, request task decomposition
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


def _attach_prompt_snapshot(lc_msgs, state, agent_config, complexity):
    """Attach a compact prompt snapshot to state for trace/eval gates."""
    try:
        from app.agent.prompt_snapshot import build_prompt_snapshot

        _resolved = agent_config.resolved_configs or {}
        _tier_key = (
            complexity.model_tier if hasattr(complexity, "model_tier") else "balanced"
        )
        _ctx_window = (_resolved.get(_tier_key) or {}).get("context_window")
        prompt_version = (
            state.get("prompt_version")
            or _resolve_prompt_version(getattr(agent_config, "agent_code", None))
            or "runtime"
        )
        snapshot = build_prompt_snapshot(
            lc_msgs,
            prompt_version=str(prompt_version),
            max_total_tokens=_ctx_window,
        )
        state["prompt_snapshot"] = snapshot.to_dict()
        if snapshot.warnings:
            logger.warning("[PromptSnapshot] warnings=%s", snapshot.warnings[:5])
    except Exception as e:
        logger.debug("[PromptBuilder] prompt snapshot skipped: %s", e)


def _resolve_prompt_version(agent_code: str | None) -> str:
    try:
        from app.services.prompt_registry import prompt_registry

        return prompt_registry.resolve_prompt_version(agent_code)
    except Exception:
        return agent_code or "runtime"
