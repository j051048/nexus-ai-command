"""
Intent Router — classifies user query complexity and selects the optimal model.

This runs as the FIRST node in the graph. It performs:
1. Fast keyword / heuristic classification (zero LLM cost)
2. Optional LLM-based classification for ambiguous queries
3. Model selection based on complexity tier

Complexity tiers:
  SIMPLE   → greetings, small-talk, simple FAQ     → gpt-4o-mini
  MODERATE → single-tool lookups, status queries    → gpt-4o-mini
  COMPLEX  → multi-step analysis, reports           → gpt-4o
  CRITICAL → approvals, financial mutations         → gpt-4o + HITL gate
"""

import json
import re
import logging
from typing import Tuple

from langchain_core.messages import HumanMessage

from app.agent.state import AgentState, AgentPhase, QueryComplexity, ThinkingStep
from app.core.config import settings

logger = logging.getLogger(__name__)

# ─── Keyword Patterns ────────────────────────────────────────────────────────

_GREETING_PATTERNS = re.compile(
    r"^(你好|hi|hello|hey|嗨|早上好|下午好|晚上好|在吗|你是谁|介绍一下|帮我|谢谢|好的|了解|明白|ok|thanks)[\s!！?？。.]*$",
    re.IGNORECASE,
)

_CRITICAL_KEYWORDS = {
    "approve", "reject", "批准", "拒绝", "审批", "批了", "不批",
    "同意", "驳回", "通过", "报销", "付款", "转账", "发工资",
    "发公告", "全员通知", "删除", "解雇", "开除", "降职",
}

_COMPLEX_KEYWORDS = {
    "分析", "对比", "趋势", "预测", "报告", "总结", "统计",
    "仪表盘", "dashboard", "经营", "绩效排名", "竞品",
    "招标", "投标", "tender", "battlecard", "战报",
    "多少人", "本月业绩", "团队表现", "环比", "同比",
}

_MODERATE_KEYWORDS = {
    "查询", "查一下", "看看", "请假", "考勤", "项目", "进度",
    "预算", "剩余", "工资", "薪资", "会议", "日程", "任务",
    "商机", "线索", "客户", "合同", "知识库", "搜索",
}


def classify_query(query: str) -> Tuple[QueryComplexity, str]:
    """
    Fast heuristic classification of user intent.

    Returns:
        (complexity, intent_summary)
    """
    text = query.strip().lower()

    # 1. Greetings / trivial
    if _GREETING_PATTERNS.match(text) or len(text) < 5:
        return QueryComplexity.SIMPLE, "简单问候或闲聊"

    # 2. Critical (irreversible operations)
    matched_critical = _CRITICAL_KEYWORDS & set(
        re.findall(r"[\w]+", text)
    )
    if matched_critical:
        return QueryComplexity.CRITICAL, f"关键操作: {', '.join(matched_critical)}"

    # 3. Complex (multi-step analysis)
    words = set(re.findall(r"[\w]+", text))
    matched_complex = _COMPLEX_KEYWORDS & words
    if matched_complex or len(text) > 200:
        return QueryComplexity.COMPLEX, f"复杂分析: {', '.join(matched_complex) if matched_complex else '长文本'}"

    # 4. Moderate (single-tool operations)
    matched_moderate = _MODERATE_KEYWORDS & words
    if matched_moderate:
        return QueryComplexity.MODERATE, f"工具查询: {', '.join(matched_moderate)}"

    # 5. Default: moderate (let the LLM decide tool usage)
    return QueryComplexity.MODERATE, "一般业务查询"


# ─── LLM-based Intent Classification ────────────────────────────────────────

async def _llm_classify_intent(
    query: str,
    config,
) -> Tuple[QueryComplexity, str]:
    """
    Use LLM for ambiguous query classification.

    Falls back to MODERATE if LLM fails.
    """
    from langchain_openai import ChatOpenAI

    prompt = f"""请分析以下用户输入的复杂度提示，并将其分类为:
- simple: 闲聊、简单问候
- moderate: 单一工具查询、简单指令
- complex: 多步骤分析、综合报告、长文本处理
- critical: 涉及审批、金钱、敏感人事操作

用户输入: {query}

返回格式示例: {{"complexity": "moderate", "reason": "查询单个项目进度"}}
"""

    try:
        llm = ChatOpenAI(
                model=config.mini_model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=0.0,
            timeout=10.0,
    )
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content or "{}"

        # Extract JSON from response
        json_match = re.search(r'\{[^}]+\}', content)
        if json_match:
            data = json.loads(json_match.group())
            complexity_str = data.get("complexity", "moderate")
            if complexity_str in [c.value for c in QueryComplexity]:
                return QueryComplexity(complexity_str), f"LLM 识别: {data.get('reason', '未知原因')}"
    except Exception as e:
        logger.debug(f"[Router] LLM intent classification failed: {e}")

    return QueryComplexity.MODERATE, "一般业务查询 (LLM 分类失败)"


# ─── Router Node ─────────────────────────────────────────────────────────────

async def route_node(state: AgentState) -> dict:
    """
    LangGraph node: Classify user intent and pick the optimal model.
    """
    config = state["config"]
    messages = state.get("messages", [])

    # Extract last user message
    last_user_msg = ""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            last_user_msg = msg.content
            break
        elif isinstance(msg, dict) and msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    complexity, intent_summary = classify_query(last_user_msg)
    
    # ── LLM Fallback for ambiguous queries ──
    if intent_summary == "一般业务查询" and len(last_user_msg) > 10:
        complexity, intent_summary = await _llm_classify_intent(last_user_msg, config)

    selected_model = config.get_model_for_complexity(complexity)

    logger.info(
        f"[Router] user={config.user_id} complexity={complexity.value} "
        f"model={selected_model} intent='{intent_summary}'"
    )

    thinking_step = ThinkingStep(
        phase=AgentPhase.ROUTING.value,
        content=f"意图分类: {intent_summary} → 复杂度: {complexity.value} → 模型: {selected_model}",
    )

    return {
        "complexity": complexity,
        "selected_model": selected_model,
        "intent_summary": intent_summary,
        "current_phase": AgentPhase.PLANNING,
        "thinking_steps": [thinking_step],
    }