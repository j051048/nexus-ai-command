"""
Graph Node: synthesize_node — lightweight tool result synthesis.

Replaces the expensive Plan→(bind_tools + full system prompt) second-pass
with a focused mini_model call that only sees the user question + tool results.

Triggered when: execute completes with all tools successful.
- SIMPLE/MODERATE: minimal prompt, ~60% token savings
- COMPLEX/CRITICAL: enhanced prompt with inline critic self-evaluation,
  eliminating separate critic_node LLM call (3→2 total LLM calls)
"""

import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent.node_helpers import (
    AgentConfig,
    AgentPhase,
    AgentState,
    QueryComplexity,
    ThinkingStep,
    _get_llm,
    invoke_with_fallback,
    logger,
    record_hallucination,
)

# ── Inline grounding check (ported from reflect_node Layer 3) ────────────────

_DATE_PATTERNS = [
    re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*[日号]?"),
    re.compile(r"\d{4}\s*-\s*\d{1,2}\s*-\s*\d{1,2}"),
    re.compile(r"\d{1,2}\s*:\s*\d{1,2}(?:\s*:\s*\d{1,2})?"),
    re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"),
    re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
]


def _strip_dates(text: str) -> str:
    for pat in _DATE_PATTERNS:
        text = pat.sub("", text)
    return text


def _verify_grounding(ai_response: str, tool_results: list) -> str | None:
    """Quick grounding check: verify numbers in response match tool results."""
    clean_ai = _strip_dates(ai_response)
    ai_numbers = re.findall(r"\d+(?:\.\d+)?", clean_ai)

    tool_numbers = []
    for tc in tool_results:
        result_text = tc.result if hasattr(tc, "result") else tc.get("result", "")
        if result_text:
            tool_numbers.extend(re.findall(r"\d+(?:\.\d+)?", _strip_dates(str(result_text))))

    if not tool_numbers:
        return None

    issues = []
    for num in ai_numbers:
        if float(num) < 10:
            continue
        found = any(abs(float(num) - float(tn)) / max(float(tn), 1.0) < 0.10 for tn in tool_numbers)
        if not found:
            issues.append(f"数值 {num} 未见工具返回")

    if len(issues) >= 3:
        return "; ".join(issues[:3])
    return None


# ── System prompts ───────────────────────────────────────────────────────────

_SIMPLE_SYSTEM_PROMPT = (
    "你是企业AI助手。根据工具执行结果，直接回答用户的问题。\n"
    "要求：先说结论，简洁准确，数据原封不动引用工具结果。\n"
    "禁止：不要说'根据查询结果'、'让我为您'等废话。直接给答案。"
)

_COMPLEX_SYSTEM_PROMPT = (
    "你是企业AI助手。根据工具执行结果，给出完整、有深度的回答。\n\n"
    "## 回答要求\n"
    "1. 先说核心结论，再展开分析\n"
    "2. 数据必须原封不动引用工具结果，严禁编造数字\n"
    "3. 多个工具结果需交叉整合，给出综合判断\n"
    "4. 适当给出行动建议或下一步操作\n\n"
    "## 质量自检（内部执行，不输出）\n"
    "回答前请自检：\n"
    "- 完整性：是否覆盖了用户所有问题点？\n"
    "- 准确性：所有数值是否与工具返回完全一致？\n"
    "- 相关性：是否紧扣用户意图，没有跑题？\n"
    "如有不达标项，立即修正后再输出。\n\n"
    "禁止：不要说'根据查询结果'、'让我为您'等废话。直接给答案。"
)


async def synthesize_node(state: AgentState) -> dict:
    """
    Lightweight synthesis of tool results into a user-facing response.

    Unlike plan_node's second pass, this node:
    - Does NOT bind tools (no chance of triggering more tool calls)
    - Does NOT inject full system prompt / RAG / few-shot
    - Uses mini_model regardless of complexity
    - Only sends: brief system instruction + user question + tool results

    For COMPLEX/CRITICAL queries, the prompt includes critic self-evaluation
    instructions, eliminating the need for a separate critic_node LLM call.

    This saves ~60% of tokens compared to a full plan_node round-trip.
    """
    config: AgentConfig = state["config"]
    completed_tools = state.get("completed_tool_calls", [])
    messages = state.get("messages", [])
    complexity = state.get("complexity", QueryComplexity.MODERATE)

    # Extract user's original question
    user_question = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_question = msg.content
            break
        elif isinstance(msg, dict) and msg.get("role") == "user":
            user_question = msg.get("content", "")
            break

    # Build concise tool results summary
    tool_parts = []
    for tc in completed_tools:
        name = tc.tool_name if hasattr(tc, "tool_name") else tc.get("tool_name", "")
        # COMPLEX gets more context per tool (1200 chars vs 800)
        max_len = 1200 if complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL) else 800
        result = (tc.result if hasattr(tc, "result") else tc.get("result", ""))[:max_len]
        status = tc.status if hasattr(tc, "status") else tc.get("status", "")
        if status == "success":
            tool_parts.append(f"【{name}】\n{result}")

    tool_summary = "\n\n".join(tool_parts)

    # Select prompt based on complexity
    is_complex = complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL)
    system_prompt = _COMPLEX_SYSTEM_PROMPT if is_complex else _SIMPLE_SYSTEM_PROMPT

    synthesis_msgs = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=(
            f"用户问题：{user_question}\n\n"
            f"工具执行结果：\n{tool_summary}"
        )),
    ]

    try:
        llm = _get_llm(config, model=config.mini_model, streaming=True)
        ai_msg = await invoke_with_fallback(
            llm, synthesis_msgs, config=config, model=config.mini_model, streaming=True,
        )
        content = ai_msg.content or ""
    except Exception as e:
        logger.error(f"[Synthesize] LLM call failed: {e}, falling back to raw tool output")
        # Fallback: just format tool results directly
        content = tool_summary if tool_summary else "工具执行完成，但无法生成摘要。"

    # ── Inline grounding check (replaces reflect Layer 3 + critic for this path) ──
    is_hallucination = False
    if content and completed_tools:
        grounding_issue = _verify_grounding(content, completed_tools)
        if grounding_issue:
            is_hallucination = True
            logger.warning(f"[Synthesize] Grounding issue detected: {grounding_issue}")
            record_hallucination("synthesize_node")
            # For COMPLEX, trigger replanning; for SIMPLE/MODERATE, just warn
            if is_complex:
                return {
                    "messages": [HumanMessage(content=f"[自我指引] 回复数据与工具返回不一致: {grounding_issue}")],
                    "reflection": f"Synthesize grounding check failed: {grounding_issue}",
                    "reflection_guidance": f"严格引用工具返回的原始数据，修正不一致数值: {grounding_issue}",
                    "is_hallucination": True,
                    "needs_replanning": True,
                    "current_phase": AgentPhase.PLANNING,
                    "iteration": state.get("iteration", 0) + 1,
                    "thinking_steps": [
                        ThinkingStep(
                            phase=AgentPhase.REFLECTING.value,
                            content=f"数据校验未通过: {grounding_issue}，触发修正",
                        )
                    ],
                }

    thinking_content = "快速合成工具结果"
    if is_complex:
        thinking_content += "（含质量自评）"
    else:
        thinking_content += "（轻量模式）"

    result = {
        "messages": [AIMessage(content=content)],
        "final_response": content,
        "current_phase": AgentPhase.RESPONDING,
        "iteration": state.get("iteration", 0),
        "thinking_steps": [
            ThinkingStep(
                phase=AgentPhase.PLANNING.value,
                content=thinking_content,
            )
        ],
    }

    # For COMPLEX, mark critic as passed (inline self-evaluation replaces separate critic)
    if is_complex:
        result["critic_passed"] = True
        result["critic_feedback"] = "内联质量自评（synthesize_node）"

    return result
