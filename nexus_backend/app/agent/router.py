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
import logging
import re

from langchain_core.messages import HumanMessage

from app.agent.state import AgentPhase, AgentState, QueryComplexity, ThinkingStep

logger = logging.getLogger(__name__)

# ─── Keyword Patterns ────────────────────────────────────────────────────────

_GREETING_PATTERNS = re.compile(
    r"^(你好|hi|hello|hey|嗨|早上好|下午好|晚上好|在吗|你是谁|介绍一下|帮我|谢谢|好的|了解|明白|ok|thanks)[\s!！?？。.]*$",
    re.IGNORECASE,
)

# Self-description / capability inquiry patterns — should be handled as SIMPLE
# without tool calls (the AI knows its own capabilities from system prompt)
_SELF_DESCRIPTION_PATTERNS = re.compile(
    r"你(能|会|可以)(做|帮|干)什么|你(有|会)哪些(技能|能力|功能)|你的(技能|能力|功能)|"
    r"能帮我做什么|你能干嘛|介绍(一下)?你(自己|的功能|的能力)",
    re.IGNORECASE,
)

# ─── Query vs Execute verb sets (for semantic distinction) ───────────────────
# When a CRITICAL keyword is matched but only query verbs are present (and no
# execute verbs), the complexity is downgraded to MODERATE — e.g. "查看通知"
# should not be treated as CRITICAL, but "发通知" should.

_QUERY_VERBS = {
    "查", "看看", "查一下", "查询", "查看", "搜索",
    "到哪了", "什么时候", "多少", "几个", "哪些", "有没有",
    "状态", "进度", "记录", "历史", "列表", "明细",
}

_EXECUTE_VERBS = {
    "申请", "创建", "发起", "提交", "发送", "发布",
    "修改", "变更", "更新", "设置",
    "批准", "拒绝", "同意", "驳回", "批了", "不批",
    "删除", "取消", "撤销", "终止",
    "执行", "操作", "处理", "办理",
}

_CRITICAL_KEYWORDS = {
    # Approval actions
    "approve",
    "reject",
    "批准",
    "拒绝",
    "审批",
    "批了",
    "不批",
    "同意",
    "驳回",
    "通过",
    # Financial mutations
    "报销",
    "付款",
    "转账",
    "发工资",
    # Announcements / notifications
    "发公告",
    "全员通知",
    "通知",
    "公告",
    # Destructive / data-security operations
    "删除",
    "批量删除",
    "数据导出",
    # HR-sensitive operations
    "解雇",
    "开除",
    "降职",
    "辞退",
    "调岗",
    "调动",
    "离职",
    "辞职",
    "升职",
    "晋升",
    # Administrative-sensitive operations
    "用印",
    "盖章",
    "签署",
    "合同终止",
}

_COMPLEX_KEYWORDS = {
    "分析",
    "对比",
    "趋势",
    "预测",
    "报告",
    "总结",
    "统计",
    "仪表盘",
    "dashboard",
    "经营",
    "绩效排名",
    "竞品",
    "招标",
    "投标",
    "tender",
    "battlecard",
    "战报",
    "多少人",
    "本月业绩",
    "团队表现",
    "环比",
    "同比",
}

_MODERATE_KEYWORDS = {
    # Query actions
    "查询",
    "查一下",
    "看看",
    # Leave / attendance
    "请假",
    "考勤",
    "出差",
    "补卡",
    "打卡",
    "加班",
    # Project / task
    "项目",
    "进度",
    "任务",
    # Finance / budget
    "预算",
    "剩余",
    "工资",
    "薪资",
    "发票",
    "开票",
    # Scheduling
    "会议",
    "日程",
    "订餐",
    # CRM / sales
    "商机",
    "线索",
    "客户",
    "合同",
    # Supply chain / procurement
    "供应商",
    "采购",
    # Administrative / logistics
    "快递",
    "寄件",
    "设备",
    "资产",
    "车辆",
    "用车",
    "印章",
    "访客",
    # Document / knowledge
    "公文",
    "发文",
    "收文",
    "档案",
    "知识库",
    "搜索",
    # HR / training
    "培训",
    "通讯录",
}

# ─── VMD Agent Role Detection Patterns ────────────────────────────────────────
# Maps regex patterns to agent_code + scene_code.
# Checked AFTER complexity classification; used to assign a specific agent role.

_AGENT_ROLE_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # (pattern, agent_code, scene_code)
    # Content marketing
    (
        re.compile(r"白皮书|案例文章|内容营销|SEO|文案|公众号|社交媒体|技术文档|软文", re.IGNORECASE),
        "content_agent",
        "content_creation",
    ),
    # Visual design
    (
        re.compile(r"视觉设计|海报|画册|展板|Banner|物料设计|品牌视觉|VI设计|宣传物料", re.IGNORECASE),
        "design_agent",
        "visual_design",
    ),
    # Media placement
    (
        re.compile(r"媒介投放|广告投放|SEM|信息流|渠道分析|媒介策略|投放预算|ROI优化", re.IGNORECASE),
        "media_agent",
        "media_planning",
    ),
    # Lead generation / clue
    (
        re.compile(r"线索获取|获客|线索评分|渠道归因|CAC|获客成本|MQL|SQL|线索培育", re.IGNORECASE),
        "clue_agent",
        "lead_generation",
    ),
    # Sales enablement
    (
        re.compile(r"销售话术|Battlecard|报价策略|竞品对比|销售培训|赢单|丢单|投标策略|标书", re.IGNORECASE),
        "sales_agent",
        "sales_enablement",
    ),
    # R&D-production-sales synergy
    (
        re.compile(r"研产销|新品上市|GTM|跨部门|产销协同|需求传递|VOC|产品发布", re.IGNORECASE),
        "synergy_agent",
        "rd_marketing_sync",
    ),
    # Private domain operation
    (
        re.compile(r"私域|社群运营|会员体系|客户旅程|复购|客户留存|NPS|社群", re.IGNORECASE),
        "operation_agent",
        "private_domain",
    ),
    # PR / reputation
    (re.compile(r"舆情|口碑|危机公关|品牌监控|负面|舆论|KOL|声誉", re.IGNORECASE), "pr_agent", "brand_monitoring"),
    # Compliance
    (
        re.compile(r"合规|广告法|审核|绝对化用语|极限词|医疗器械广告|内容审查", re.IGNORECASE),
        "compliance_agent",
        "ad_compliance",
    ),
    # Tender / bidding (may overlap with sales)
    (re.compile(r"标书|投标|招标|评标|中标|开标", re.IGNORECASE), "sales_agent", "proposal"),
]

# Patterns that suggest the query needs multi-agent orchestration (WBS decomposition)
_MULTI_AGENT_PATTERNS = re.compile(
    r"营销方案|营销计划|推广方案|市场策略|整合营销|全案|年度计划|季度计划|Go.?to.?Market|上市计划|品牌策划|完整方案",
    re.IGNORECASE,
)


def detect_agent_role(query: str, complexity: QueryComplexity) -> tuple[str, str, bool]:
    """
    Detect which VMD agent role should handle this query.

    Returns:
        (agent_code, scene_code, needs_multi_agent)

    For simple/moderate queries or no match, returns ("", "", False) — meaning
    the standard plan/execute flow handles it without a specific VMD role.
    """
    text = query.strip()

    # Simple queries don't need role routing
    if complexity == QueryComplexity.SIMPLE:
        return "", "", False

    # Check for multi-agent orchestration first
    needs_multi_agent = bool(_MULTI_AGENT_PATTERNS.search(text)) and complexity == QueryComplexity.COMPLEX

    # If multi-agent orchestration is needed, always route to director for WBS decomposition
    # The director will delegate to specific agents via the orchestrator
    if needs_multi_agent:
        return "director_agent", "task_decompose", True

    # Detect specific agent role for single-agent scenarios
    for pattern, agent_code, scene_code in _AGENT_ROLE_PATTERNS:
        if pattern.search(text):
            return agent_code, scene_code, False

    return "", "", False


def classify_query(query: str) -> tuple[QueryComplexity, str]:
    """
    Fast heuristic classification of user intent.

    Returns:
        (complexity, intent_summary)
    """
    text = query.strip().lower()

    # 1. Greetings / trivial
    # Note: threshold=2 because Chinese is compact — "批了"(2 chars) is a valid CRITICAL command
    if _GREETING_PATTERNS.match(text) or len(text) < 2:
        return QueryComplexity.SIMPLE, "简单问候或闲聊"

    # 1b. Self-description / capability inquiry — answer from system prompt, no tools needed
    if _SELF_DESCRIPTION_PATTERNS.search(text):
        return QueryComplexity.SIMPLE, "AI自我介绍或能力说明"

    # 2. Critical (irreversible operations)
    # P1 Fix: Use substring matching instead of word splitting to avoid
    # Chinese tokenization issues (e.g., "不批准" being split into "不" + "批准")
    matched_critical = {kw for kw in _CRITICAL_KEYWORDS if kw in text}
    if matched_critical:
        # Semantic distinction: "查看审批" (query) vs "批准审批" (execute)
        # If only query verbs present and no execute verbs → downgrade to MODERATE
        has_query_verb = any(v in text for v in _QUERY_VERBS)
        has_execute_verb = any(v in text for v in _EXECUTE_VERBS)
        if has_query_verb and not has_execute_verb:
            return QueryComplexity.MODERATE, f"查询操作(含敏感词但为只读): {', '.join(matched_critical)}"
        return QueryComplexity.CRITICAL, f"关键操作: {', '.join(matched_critical)}"

    # 3. Complex (multi-step analysis)
    matched_complex = {kw for kw in _COMPLEX_KEYWORDS if kw in text}
    if matched_complex or len(text) > 200:
        return QueryComplexity.COMPLEX, f"复杂分析: {', '.join(matched_complex) if matched_complex else '长文本'}"

    # 4. Moderate (single-tool operations)
    matched_moderate = {kw for kw in _MODERATE_KEYWORDS if kw in text}
    if matched_moderate:
        return QueryComplexity.MODERATE, f"工具查询: {', '.join(matched_moderate)}"

    # 5. Default: moderate (let the LLM decide tool usage)
    return QueryComplexity.MODERATE, "一般业务查询"


# ─── LLM-based Intent Classification ────────────────────────────────────────


async def _llm_classify_intent(
    query: str,
    config,
) -> tuple[QueryComplexity, str]:
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
        # Resolve via LLM gateway
        resolved = None
        try:
            from app.services.llm_helpers import resolve_model_config

            org_id = getattr(config, "org_id", None) or "default"
            resolved = await resolve_model_config(org_id)
        except Exception:
            logger.debug("LLM gateway model config unavailable in router, using default")

        if resolved:
            llm = ChatOpenAI(
                model=resolved.get("model", config.mini_model),
                api_key=resolved["api_key"],
                base_url=resolved["base_url"],
                temperature=0.0,
                timeout=10.0,
            )
        else:
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
        json_match = re.search(r"\{[^}]+\}", content)
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

    # ── VMD Agent Role Detection (additive) ──
    agent_code, scene_code, needs_multi_agent = detect_agent_role(last_user_msg, complexity)

    if agent_code:
        logger.info(
            f"[Router] VMD role detected: agent_code={agent_code} scene={scene_code} "
            f"multi_agent={needs_multi_agent}"
        )

    logger.info(
        f"[Router] user={config.user_id} complexity={complexity.value} "
        f"model={selected_model} intent='{intent_summary}'"
    )

    thinking_step = ThinkingStep(
        phase=AgentPhase.ROUTING.value,
        content=f"意图分类: {intent_summary} → 复杂度: {complexity.value} → 模型: {selected_model}"
        + (f" → Agent: {agent_code}" if agent_code else ""),
    )

    result = {
        "complexity": complexity,
        "selected_model": selected_model,
        "intent_summary": intent_summary,
        "current_phase": AgentPhase.PLANNING,
        "thinking_steps": [thinking_step],
    }

    # Write VMD role info into state (only if detected)
    if agent_code:
        result["agent_code"] = agent_code
        result["scene_code"] = scene_code

    return result
