"""
Graph Nodes: respond_node, simple_respond_node, error_node, _mask_sensitive_fields, response post-processing
"""

import re as _re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage  # noqa: F401

from app.agent.node_helpers import (
    AgentConfig,
    AgentPhase,
    AgentState,
    ThinkingStep,
    _get_llm,
    _messages_to_lc_format,
    invoke_with_fallback,
    logger,
    plugin_system_service,
    sanitize_output,
)
from app.services.plugin_system_service import ExtensionPoint

# ═══════════════════════════════════════════════════════════════════════════════
#  HELPER: Role-based Sensitive Field Masking
# ═══════════════════════════════════════════════════════════════════════════════

# Sensitive field patterns with role access levels
# Only roles at or above the specified level can see unmasked values
_SENSITIVE_FIELD_RULES = [
    # (pattern, mask_replacement, minimum_role_level)
    # Role levels: guest=0, employee=1, manager=2, boss=3, founder=4
    (_re.compile(r"(薪[资酬水]|工资|月薪|年薪|底薪|基本工资)\s*[:：]?\s*[\d,.]+\s*[元万千]?"), "[薪资信息已隐藏]", 3),
    (_re.compile(r"(提成|奖金|绩效奖|年终奖)\s*[:：]?\s*[\d,.]+\s*[元万千]?"), "[奖金信息已隐藏]", 3),
    (_re.compile(r"(社保|公积金|五险一金)\s*[:：]?\s*[\d,.]+\s*[元万千]?"), "[社保信息已隐藏]", 3),
    (_re.compile(r"(合同金额|签约金额|合同价)\s*[:：]?\s*[\d,.]+\s*[元万千]?"), "[合同金额已隐藏]", 2),
    (_re.compile(r"(成本价|进货价|底价)\s*[:：]?\s*[\d,.]+\s*[元万千]?"), "[成本信息已隐藏]", 2),
    (_re.compile(r"(利润率|毛利率|净利率)\s*[:：]?\s*[\d,.]+\s*%?"), "[利润信息已隐藏]", 2),
]

_ROLE_LEVELS = {
    "guest": 0,
    "employee": 1,
    "manager": 2,
    "boss": 3,
    "founder": 4,
}


def _mask_sensitive_fields(content: str, user_role: str) -> str:
    """
    P1 Security: Mask sensitive financial/HR fields based on user role.

    Higher-privilege roles see more data. Lower-privilege roles get
    sensitive fields replaced with '[已隐藏]' placeholders.
    """
    if not content or not user_role:
        return content

    current_level = _ROLE_LEVELS.get(user_role, 1)

    for pattern, replacement, min_level in _SENSITIVE_FIELD_RULES:
        if current_level < min_level:
            content = pattern.sub(replacement, content)

    return content


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPER: Response Post-Processing Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

# Redundant opening phrases to strip (LLM habits)
_REDUNDANT_OPENINGS = _re.compile(
    r"^(?:"
    r"好的[，,\s]*|"
    r"当然[，,\s]*(?:可以[，,\s]*)?|"
    r"没问题[，,\s]*|"
    r"我来帮您[，,\s]*|"
    r"让我(?:来)?为您[^\n。，]{0,10}[，,\s]*|"
    r"我(?:已经)?(?:帮您|为您)[^\n。，]{0,10}[，,\s]*|"
    r"我明白了[，,\s]*|"
    r"收到[，,\s]*|"
    r"嗯[，,\s]*"
    r")",
    _re.MULTILINE,
)

# Redundant closing phrases to strip
_REDUNDANT_CLOSINGS = _re.compile(
    r"(?:"
    r"如(?:果)?(?:您)?(?:还)?需要.*(?:帮助|协助).*|"
    r"还有什么.*(?:帮|问|需要).*|"
    r"希望(?:以上)?(?:内容)?(?:对您)?有所帮助.*|"
    r"如有(?:任何)?(?:疑问|问题).*(?:联系|告知|咨询).*|"
    r"祝您?工作顺利.*"
    r")[。！!]?\s*$",
    _re.MULTILINE,
)

# AI self-reference phrases to strip mid-text
_AI_SELF_REFS = _re.compile(
    r"作为(?:一[个位])?(?:AI|人工智能)?助手[，,\s]*"
)

# Pattern: key metric with number + unit (for bolding)
_KEY_METRIC = _re.compile(
    r"(?<!\*\*)("  # Not already bolded
    r"[¥￥$]?\s*[\d,]+(?:\.\d+)?\s*(?:万|亿|千|百|元|%|件|次|人|单|笔|天|个月|家)"
    r")(?!\*\*)"
)

# Pattern: consecutive items separated by 、(for list conversion)
_CONSECUTIVE_ITEMS = _re.compile(
    r"(?:(?:[\u4e00-\u9fff\w]+)(?:、))+(?:[\u4e00-\u9fff\w]+)"
)


def _strip_redundant_phrases(text: str) -> str:
    """Remove common LLM verbose opening/closing phrases.

    Strips: "好的，我来帮您...", "如需其他帮助...", "作为AI助手..." etc.
    Preserves content between gen-ui code blocks.
    """
    if not text:
        return text

    # Don't process gen-ui blocks
    if "```gen-ui" in text:
        # Split around gen-ui blocks, only process non-block parts
        parts = _re.split(r"(```gen-ui[\s\S]*?```)", text)
        processed = []
        for i, part in enumerate(parts):
            if part.startswith("```gen-ui"):
                processed.append(part)
            else:
                part = _REDUNDANT_OPENINGS.sub("", part, count=1)
                part = _REDUNDANT_CLOSINGS.sub("", part)
                part = _AI_SELF_REFS.sub("", part)
                processed.append(part)
        return "".join(processed).strip()

    text = _REDUNDANT_OPENINGS.sub("", text, count=1)
    text = _REDUNDANT_CLOSINGS.sub("", text)
    text = _AI_SELF_REFS.sub("", text)
    return text.strip()


def _enhance_formatting(text: str) -> str:
    """Enhance response formatting for readability.

    - Bold key metrics (numbers with units)
    - Convert long comma/顿号 lists into markdown bullet lists
    Only applies to longer responses (>200 chars) without existing formatting.
    """
    if not text or len(text) < 200:
        return text

    # Skip if already has rich formatting (markdown headers, lists, gen-ui)
    if _re.search(r"^#{1,3}\s|^\s*[-*]\s|```gen-ui", text, _re.MULTILINE):
        return text

    # Bold key metrics (numbers with units like ¥428万, 95.2%, 15人)
    text = _KEY_METRIC.sub(r"**\1**", text)

    # Convert consecutive 顿号-separated items (≥4 items) to bullet list
    def _list_convert(match):
        items_str = match.group(0)
        items = items_str.split("、")
        if len(items) >= 4:
            return "\n" + "\n".join(f"- {item}" for item in items) + "\n"
        return items_str

    text = _CONSECUTIVE_ITEMS.sub(_list_convert, text)

    return text


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE: simple_respond_node (SIMPLE fast-path, skips Plan→Execute→Reflect)
# ═══════════════════════════════════════════════════════════════════════════════


async def simple_respond_node(state: AgentState) -> dict:
    """
    Fast-path for SIMPLE queries (greetings, chitchat, FAQ).

    Directly calls mini_model without tool binding, skipping the full
    Plan→Execute→Reflect pipeline. Saves 2-3 LLM round-trips.
    """
    config: AgentConfig = state["config"]
    messages = state.get("messages", [])
    lc_msgs = _messages_to_lc_format(messages)

    # Inject anti-hallucination guard for time-sensitive topics
    # Even in SIMPLE mode, the LLM should not fabricate current events
    lc_msgs = list(lc_msgs)  # make mutable copy
    if lc_msgs and isinstance(lc_msgs[0], SystemMessage):
        lc_msgs[0] = SystemMessage(
            content=lc_msgs[0].content
            + "\n\n【重要】你没有联网能力，不知道当前的电影、新闻、天气、股价等实时信息。"
            "如果用户询问此类信息，请坦诚说明你无法获取实时数据，建议用户使用搜索引擎或相关APP查看。"
            "严禁编造具体的电影名、新闻事件、天气数据或股价数字。"
        )

    # Use mini_model for speed
    llm = _get_llm(config, model=config.mini_model, streaming=True)

    try:
        ai_msg = await invoke_with_fallback(
            llm, lc_msgs, config=config, model=config.mini_model, streaming=True,
        )
        content = ai_msg.content or ""
    except Exception as e:
        logger.error(f"[SimpleRespond] LLM call failed: {e}")
        content = ""

    # Apply post-processing pipeline (full 5-stage output scan)
    from app.services.content_moderation import sanitize_output_advanced_safe
    content = await sanitize_output_advanced_safe(content)
    from app.agent.stream import strip_think_tags
    content = strip_think_tags(content)

    # P0 Security: LLM output scanner (indirect prompt injection, PII, SQLi, XSS)
    from app.core.output_scanner import output_scanner
    scan_result = await output_scanner.scan(content)
    if not scan_result.is_safe:
        logger.warning(
            f"[SimpleRespond] Output scanner found {len(scan_result.violations)} violation(s): "
            f"{scan_result.violations[:3]}"
        )
        content = scan_result.sanitized_text

    content = _mask_sensitive_fields(content, config.user_role)
    content = _strip_redundant_phrases(content)

    return {
        "final_response": content or "你好，有什么可以帮您？",
        "current_phase": AgentPhase.DONE,
        "thinking_steps": [
            ThinkingStep(
                phase=AgentPhase.RESPONDING.value,
                content="简单问答直出（跳过工具规划）",
            )
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE: respond_node
# ═══════════════════════════════════════════════════════════════════════════════


async def respond_node(state: AgentState) -> dict:
    """
    Finalize output and format for UI.
    Includes role-based sensitive field masking for security.
    """
    final_response = state.get("final_response", "")

    if not final_response:
        from app.agent.stream import extract_clean_content
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, AIMessage) and msg.content:
                final_response = extract_clean_content(msg)
                break

    # Final moderation filter (full 5-stage output scan)
    from app.services.content_moderation import sanitize_output_advanced_safe
    final_response = await sanitize_output_advanced_safe(final_response)

    # Strip reasoning model <think>...</think> tags (belt-and-suspenders)
    from app.agent.stream import strip_think_tags
    final_response = strip_think_tags(final_response)

    # P0 Security: LLM output scanner (indirect prompt injection, PII, SQLi, XSS)
    from app.core.output_scanner import output_scanner
    scan_result = await output_scanner.scan(final_response)
    if not scan_result.is_safe:
        logger.warning(
            f"[RespondNode] Output scanner found {len(scan_result.violations)} violation(s): "
            f"{scan_result.violations[:3]}"
        )
        final_response = scan_result.sanitized_text

    # P1 Security: Role-based sensitive field masking
    # Prevents lower-privilege users from seeing sensitive data
    # that may have been retrieved by RAG or tool calls
    config: AgentConfig = state["config"]
    final_response = _mask_sensitive_fields(final_response, config.user_role)

    # Post-processing: strip verbose LLM habits and enhance formatting
    final_response = _strip_redundant_phrases(final_response)
    final_response = _enhance_formatting(final_response)

    return {
        "final_response": final_response or "抱歉，系统处理出现异常，请重试。",
        "current_phase": AgentPhase.DONE,
        "thinking_steps": [
            ThinkingStep(
                phase=AgentPhase.RESPONDING.value,
                content=f"思考路径完成，正在输出回复 (置信度: {state.get('confidence_score', 0.8):.0%})",
            )
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE: error_node
# ═══════════════════════════════════════════════════════════════════════════════


async def error_node(state: AgentState) -> dict:
    """
    Global error handler with multi-level recovery.

    P1 Fix: 3-level recovery instead of single boolean flag:
      Level 0→1: Clear failed tools, ask LLM for alternative approach
      Level 1→2: Disable tools entirely, ask for best-effort text answer
      Level 2+:  Give up gracefully with user-facing message
    """
    error_msg = state.get("error", "未知错误")
    recovery_level = state.get("error_recovery_level", 0)
    iteration = state.get("iteration", 0)

    logger.error(f"[ErrorNode] Handling error: {error_msg} (level={recovery_level}, iter={iteration})")

    # ── Persist failure for analytics ──
    try:
        from app.services.failure_log_service import failure_log_service

        config = state.get("config")
        # Classify error type from message content
        error_type = "unknown"
        msg_lower = str(error_msg).lower()
        if "timeout" in msg_lower:
            error_type = "timeout"
        elif "permission" in msg_lower or "权限" in str(error_msg):
            error_type = "permission"
        elif "loop" in msg_lower or "循环" in str(error_msg):
            error_type = "loop"

        # Extract user message
        user_message = ""
        for msg in reversed(state.get("messages", [])):
            if hasattr(msg, "type") and msg.type == "human":
                user_message = msg.content
                break

        await failure_log_service.log_failure(
            org_id=getattr(config, "org_id", None) if config else None,
            user_id=getattr(config, "user_id", None) if config else None,
            conversation_id=getattr(config, "conversation_id", None) if config else None,
            user_message=user_message or str(error_msg),
            intent_summary=state.get("intent_summary"),
            complexity=state.get("complexity", "").value if state.get("complexity") else None,
            error_type=error_type,
            error_detail=str(error_msg)[:2000],
            severity="high" if recovery_level >= 2 else "medium",
        )
    except Exception as e:
        logger.debug(f"[ErrorNode] Failed to log failure: {e}")

    # P1 Plugin: ON_ERROR hook
    try:
        await plugin_system_service.run_hooks(
            ExtensionPoint.ON_ERROR,
            {"error": error_msg, "recovery_level": recovery_level, "iteration": iteration},
        )
    except Exception as e:
        logger.debug(f"[ErrorNode] ON_ERROR hook error: {e}")

    if recovery_level == 0 and iteration < 5:
        # Extract failed tool names from recent ToolMessages for better recovery guidance
        failed_tool_names = set()
        for msg in reversed(state.get("messages", [])):
            if hasattr(msg, "type") and msg.type == "tool":
                tool_name = getattr(msg, "name", None)
                if tool_name:
                    failed_tool_names.add(tool_name)
                break  # Only look at the most recent tool message(s)

        tool_hint = ""
        if failed_tool_names:
            names_str = ", ".join(failed_tool_names)
            tool_hint = f" 失败的工具: {names_str}。请尝试不涉及此工具的替代方案。"

        # Level 1: Clear failed tools, ask LLM to try alternative approach
        return {
            "error": None,
            "error_recovery_level": 1,
            "error_recovery_attempted": True,
            "pending_tool_calls": [],
            "current_phase": AgentPhase.PLANNING,
            "messages": [
                HumanMessage(content=f"[错误恢复L1] 前序操作失败: {error_msg}。{tool_hint or '请尝试一个不涉及此错误的替代方案。'}")
            ],
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.ERROR.value,
                    content=f"恢复L1: 切换方案以避免: {error_msg}",
                )
            ],
        }
    elif recovery_level == 1 and iteration < 5:
        # Level 2: Disable tools, ask for best-effort text answer
        return {
            "error": None,
            "error_recovery_level": 2,
            "pending_tool_calls": [],
            "requires_tools": False,
            "current_phase": AgentPhase.PLANNING,
            "messages": [
                HumanMessage(
                    content="[错误恢复L2] 工具调用持续失败。请不使用任何工具，基于已有信息给出最佳回答。如信息不足请如实说明。"
                )
            ],
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.ERROR.value,
                    content=f"恢复L2: 降级为纯文本模式: {error_msg}",
                )
            ],
        }

    # Level 3: Give up gracefully
    return {
        "final_response": f"⚠️ 系统执行过程中遇到了难以恢复的问题: {error_msg}。您可以尝试换一种说法再次提问。",
        "current_phase": AgentPhase.RESPONDING,
        "thinking_steps": [
            ThinkingStep(
                phase=AgentPhase.ERROR.value,
                content=f"❌ 遇到严重故障，停止执行: {error_msg}",
            )
        ],
    }
