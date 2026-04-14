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

from app.agent.node_helpers import _get_langfuse_callbacks, _get_trace_context
from app.agent.state import AgentPhase, AgentState, QueryComplexity, ThinkingStep

logger = logging.getLogger(__name__)

# ─── Jieba word segmentation (lazy init) ─────────────────────────────────────
# Provides more accurate Chinese keyword matching than pure substring search.
# Falls back to substring matching if jieba is unavailable.
_jieba_initialized = False


def _tokenize(text: str) -> set[str]:
    """Tokenize Chinese text with jieba; falls back to original text as single-token set."""
    global _jieba_initialized
    try:
        import jieba

        if not _jieba_initialized:
            jieba.setLogLevel(logging.WARNING)
            _jieba_initialized = True
        return set(jieba.cut(text))
    except ImportError:
        return set()


# ─── Keyword Patterns ────────────────────────────────────────────────────────

_GREETING_PATTERNS = re.compile(
    r"^(你好|hi|hello|hey|嗨|早上好|下午好|晚上好|在吗|你是谁|介绍一下|帮我|谢谢|好的|了解|明白|ok|thanks)[\s!！?？。.]*$",
    re.IGNORECASE,
)

# Self-description / capability inquiry patterns — should be handled as SIMPLE
# without tool calls (the AI knows its own capabilities from system prompt)
_SELF_DESCRIPTION_PATTERNS = re.compile(
    r"你(能|会|可以)(做|帮|干|写|画|搞|处理|生成|分析)什么|"
    r"你(有|会)哪些(技能|能力|功能)|你的(技能|能力|功能)|"
    r"能帮我做什么|你能干嘛|介绍(一下)?你(自己|的功能|的能力)|"
    r"你(能|会|可以)(写|做|帮我写|帮我做|搞|处理|生成|画|分析).{0,10}(么|吗|嘛|不|没)",
    re.IGNORECASE,
)

# Chitchat / casual conversation — should be handled as SIMPLE without tools
_CHITCHAT_PATTERNS = re.compile(
    r"(聊聊天|闲聊|随便聊|无聊|讲个笑话|说个段子|"
    r"你(觉得|认为|喜欢|怎么看)|"
    r"心情(不错|不好|很好)|"
    r"早安|晚安|午安|拜拜|再见|辛苦了|加油|"
    r"哈哈|嗯嗯|嘻嘻|呵呵|好吧|算了|"
    r"周末.{0,6}(干嘛|做什么|计划|安排))",
    re.IGNORECASE,
)

# Memory / recall queries — user is asking about past conversations or memories.
# These MUST NOT be classified as SIMPLE, because skip_semantic=True would
# prevent the memory system from retrieving relevant context.
_MEMORY_RECALL_PATTERNS = re.compile(
    # Group 1: recall verb + ... + action verb (strict: "记得...说过/聊过")
    r"(记得|记住|还记得|回忆|回顾|想起|忘记|忘了|"
    r"上次|昨天|之前|以前|过去).{0,15}"
    r"(说过|问过|聊过|提到|讨论|告诉|对话|谈过|交流|沟通|讲过|分享)|"
    # Group 2: temporal + conversation nouns ("上次对话")
    r"(之前|上次|昨天|以前|过去|历史).{0,10}(对话|聊天|交流|沟通|记录)|"
    # Group 3: "我X过什么"
    r"我(说|问|提|聊|讲)过什么|"
    # Group 4: "你记得" questions
    r"你(还)?记(得|住)|"
    # Group 5: "我们之前"
    r"我们(之前|上次|昨天)|"
    # Group 6: "记得/还记得 X 么/吗/？" — recall question with question marker
    #   e.g. "还记得我的2个同学么", "记得林凯吗"
    r"(还)?(记得|记不记得).{0,20}[么吗嘛？?]|"
    # Group 6b: "记不记得" — inherently a recall question, no question marker needed
    r"记不记得|"
    # Group 7: "之前提/说/聊过的 X" — temporal + past-tense verb + "的"
    #   e.g. "我之前提过的林凯", "上次说过的方案"
    r"(之前|上次|以前|过去|昨天).{0,6}(提|说|聊|讲|讨论)过的|"
    # Group 8: "你知道我的X吗" — knowledge recall about personal context
    r"你知道我的.{1,10}[么吗嘛？?]",
    re.IGNORECASE,
)

# Long-form writing / content creation patterns — COMPLEX tier.
# Must be checked BEFORE _REALTIME_INFO_PATTERNS because queries like
# "写一篇3000字FD-F1560食品安全推广软文" can accidentally match realtime
# patterns (推荐 regex) and get misclassified as MODERATE.
_LONGFORM_WRITING_RE = re.compile(
    r"(\d{3,}\s*字|千字|万字|长文)"  # word-count indicators
    r"|写一[篇份个]"  # "写一篇..."
    r"|(软文|推广文|公众号文案|营销文案)"  # content types
    r"|(方案书|策划案|策划书)"  # formal documents
    r"|编写.{0,10}(报告|方案|计划|总结)"  # "编写XX报告"
    r"|撰写.{0,10}(文章|报告|方案)"  # "撰写XX文章"
    r"|(写|生成|创作).{0,6}(文章|报告|文案|剧本|小说|故事)",  # "写/生成XX文章"
    re.IGNORECASE,
)

# Queries that need real-time/web information — should use web_search tool (MODERATE)
# These look like casual chat but the LLM will hallucinate without current data
_REALTIME_INFO_PATTERNS = re.compile(
    r"(推荐.{0,4}(书|电影|歌|音乐|片|剧|综艺|游戏|小说)|"
    r"(电影|片子|剧|综艺|动漫).{0,6}(推荐|好看|上映|上线|新出|热门|排行|评分)|"
    r"(新上|最近|最新|热映|正在播|刚出|好看).{0,6}(电影|片|剧|综艺|动漫|游戏|歌|小说)|"
    r"(今天|明天|后天|这周|本周|周末).{0,4}天气|天气.{0,4}(怎么样|如何|好不好|预报)|"
    r"(新闻|时事|热点|热搜|头条)|"
    r"(搜一下|搜一搜|搜索一下|查一下|查一查|帮我搜|帮我查|百度|谷歌|google)|"
    r"(股价|股票|行情|大盘|指数|涨|跌).{0,4}(多少|怎么样|如何|最新)|"
    r"(比赛|赛事|比分|战绩|赛程).{0,4}(结果|怎么样|谁赢))",
    re.IGNORECASE,
)

# ─── Negation prefixes ──────────────────────────────────────────────────────
# When a negation prefix immediately precedes a business keyword, the keyword
# should be suppressed.  E.g. "不需要报销了" → "报销" should NOT trigger
# financial intent.
_NEGATION_PREFIX_RE = re.compile(
    r"(不用|不需要|不要|别|没必要|取消|停止|停用|无需|不再|不想)"
)

# ─── Query vs Execute verb sets (for semantic distinction) ───────────────────
# When a CRITICAL keyword is matched but only query verbs are present (and no
# execute verbs), the complexity is downgraded to MODERATE — e.g. "查看通知"
# should not be treated as CRITICAL, but "发通知" should.

_QUERY_VERBS = {
    "查",
    "看看",
    "查一下",
    "查询",
    "查看",
    "搜索",
    "到哪了",
    "什么时候",
    "多少",
    "几个",
    "哪些",
    "有没有",
    "状态",
    "进度",
    "记录",
    "历史",
    "列表",
    "明细",
}

_EXECUTE_VERBS = {
    "申请",
    "创建",
    "发起",
    "提交",
    "发送",
    "发布",
    "修改",
    "变更",
    "更新",
    "设置",
    "批准",
    "拒绝",
    "同意",
    "驳回",
    "批了",
    "不批",
    "删除",
    "取消",
    "撤销",
    "终止",
    "执行",
    "操作",
    "处理",
    "办理",
    # HR-sensitive actions (these keywords ARE the action verb)
    "解雇",
    "开除",
    "辞退",
    "降职",
    "调岗",
    "调动",
    "升职",
    "晋升",
    # Announcement actions
    "发公告",
    "全员通知",
    "发通知",
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
    # Announcements / notifications — only actionable phrases
    # NOTE: bare "通知" and "公告" removed — too ambiguous. "通知全体员工停水"
    # is a SIMPLE instruction, not an irreversible mutation requiring HITL.
    "发公告",
    "全员通知",
    "发通知",
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
    "招投标",
    "tender",
    "battlecard",
    "战报",
    "多少人",
    "本月业绩",
    "团队表现",
    "环比",
    "同比",
    # Long-form content creation — needs power model, not mini
    "软文",
    "长文",
    "文章",
    "方案书",
    "策划案",
    "推广文",
    "千字",
    "万字",
    # Multi-step planning keywords
    "营销方案",
    "营销计划",
    "推广方案",
    "品牌推广",
    "品牌策划",
    "上市计划",
    "拜访计划",
    "客户拜访",
}

_MODERATE_KEYWORDS = {
    # Query actions
    "查询",
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
    # Scheduling / Calendar
    "会议",
    "日程",
    "日历",
    "安排",
    "空闲",
    "有空",
    "订餐",
    # CRM / sales
    "商机",
    "线索",
    "客户",
    "合同",
    "销售",
    "业绩",
    "营收",
    "收入",
    "成交",
    "回款",
    "订单",
    "转化率",
    "跟进率",
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
    # Audit / security
    "审计",
    "审计日志",
    "安全审计",
    # User preferences
    "偏好",
    "通知设置",
    # CRM / Business Intelligence additions
    "概况",
    "看板",
    "概览",
    "业务",
    "简报",
    # VMD / marketing domain
    "媒介",
    "投放",
    "广告",
    "合规",
}

# ─── Aggregate business indicators ─────────────────────────────────────────
# Union of ALL business keywords. Queries not matching any of these are
# treated as general conversation (SIMPLE) — no tools, no RAG.
_ALL_BUSINESS_KEYWORDS: set[str] = (
    _CRITICAL_KEYWORDS
    | _COMPLEX_KEYWORDS
    | _MODERATE_KEYWORDS
    | {
        # From _KEYWORD_DOMAIN_MAP but missing in the above sets
        "待办",
        "日报",
        "周报",
        "简报",
        "定时",
        "工单",
        "排班",
        "交接",
        "跟进",
        "漏斗",
        "招聘",
        "绩效",
        "员工",
        "部门",
        "入职",
        "标书",
        "白皮书",
        "文案",
        "话术",
        "手册",
        "市场",
        "舆情",
        "证照",
        "通知",
        "公告",
        "概况",
        "看板",
        "概览",
        "详情",
        "CRM",
        # Document/knowledge terms that suggest RAG-worthy queries
        "产品",
        "文档",
        "资料",
        "方案",
        "规范",
        "规格",
        "完成",
        "工作",
        "概括",
        "总结",
        "历史",
        "记录",
        "回忆",
        "记得",
    }
)

# ─── DB-loaded keyword overlay ────────────────────────────────────────────
# Loaded once from the intent_rules table (if available) and merged into
# the hardcoded sets above. Cached module-level to avoid repeated DB calls.
_db_keywords_loaded = False


async def _load_db_intent_rules() -> None:
    """Load keyword rules from intent_rules table and merge into hardcoded sets.

    Called once on first classify_query invocation. Falls back silently to
    hardcoded keywords if the table doesn't exist or the DB is unavailable.
    """
    global _db_keywords_loaded
    if _db_keywords_loaded:
        return
    _db_keywords_loaded = True

    try:
        from app.core.database import supabase

        if not supabase:
            return

        res = (
            await supabase.table("intent_rules")
            .select("keyword, complexity")
            .eq("is_active", True)
            .is_("tenant_id", "null")
            .execute()
        )
        if not res.data:
            return

        _complexity_map = {
            "critical": _CRITICAL_KEYWORDS,
            "complex": _COMPLEX_KEYWORDS,
            "moderate": _MODERATE_KEYWORDS,
        }
        count = 0
        for row in res.data:
            target_set = _complexity_map.get(row["complexity"])
            if target_set is not None:
                target_set.add(row["keyword"])
                _ALL_BUSINESS_KEYWORDS.add(row["keyword"])
                count += 1

        if count:
            logger.info(f"[Router] Loaded {count} intent rules from DB")
    except Exception as e:
        logger.debug(
            f"[Router] intent_rules table not available, using hardcoded keywords: {e}"
        )


async def reload_db_intent_rules() -> int:
    """强制重新加载 DB 意图规则（用于管理界面保存后调用）

    Returns: 加载的规则数量
    """
    global _db_keywords_loaded
    _db_keywords_loaded = False
    await _load_db_intent_rules()
    return sum(1 for _ in _ALL_BUSINESS_KEYWORDS)


# Maps regex patterns to agent_code + scene_code.
# Checked AFTER complexity classification; used to assign a specific agent role.

_AGENT_ROLE_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # (pattern, agent_code, scene_code)
    # Content marketing
    (
        re.compile(
            r"白皮书|案例文章|内容营销|SEO|文案|公众号|社交媒体|技术文档|软文|推广文|长文|方案书|策划案",
            re.IGNORECASE,
        ),
        "content_agent",
        "content_generation",
    ),
    # Visual design
    (
        re.compile(
            r"视觉设计|海报|画册|展板|Banner|物料设计|品牌视觉|VI设计|宣传物料",
            re.IGNORECASE,
        ),
        "design_agent",
        "visual_design",
    ),
    # Media placement
    (
        re.compile(
            r"媒介投放|广告投放|SEM|信息流|渠道分析|媒介策略|投放预算|ROI优化",
            re.IGNORECASE,
        ),
        "media_agent",
        "media_planning",
    ),
    # Lead generation / clue
    (
        re.compile(
            r"线索获取|获客|线索评分|渠道归因|CAC|获客成本|MQL|SQL|线索培育",
            re.IGNORECASE,
        ),
        "clue_agent",
        "lead_generation",
    ),
    # Sales enablement
    (
        re.compile(
            r"销售话术|Battlecard|报价策略|竞品对比|销售培训|赢单|丢单|投标策略|标书",
            re.IGNORECASE,
        ),
        "sales_agent",
        "sales_enablement",
    ),
    # R&D-production-sales synergy
    (
        re.compile(
            r"研产销|新品上市|GTM|跨部门|产销协同|需求传递|VOC|产品发布", re.IGNORECASE
        ),
        "synergy_agent",
        "rd_marketing_sync",
    ),
    # Private domain operation
    (
        re.compile(
            r"私域|社群运营|会员体系|客户旅程|复购|客户留存|NPS|社群", re.IGNORECASE
        ),
        "operation_agent",
        "private_domain",
    ),
    # PR / reputation
    (
        re.compile(r"舆情|口碑|危机公关|品牌监控|负面|舆论|KOL|声誉", re.IGNORECASE),
        "pr_agent",
        "brand_monitoring",
    ),
    # Compliance
    (
        re.compile(
            r"合规|广告法|审核|绝对化用语|极限词|医疗器械广告|内容审查", re.IGNORECASE
        ),
        "compliance_agent",
        "ad_compliance",
    ),
    # Tender / bidding (may overlap with sales)
    (
        re.compile(r"标书|投标|招标|招投标|评标|中标|开标", re.IGNORECASE),
        "sales_agent",
        "tender_analysis",
    ),
]

# Patterns that suggest the query needs multi-agent orchestration (WBS decomposition)
_MULTI_AGENT_PATTERNS = re.compile(
    r"营销方案|营销计划|推广方案|市场策略|整合营销|全案|年度计划|季度计划"
    r"|Go.?to.?Market|上市计划|品牌策划|完整方案"
    # P1: 通用复杂场景（非营销）
    r"|项目规划|出差行程|招投标全流程|产品上线|招聘计划|培训方案|年度预算"
    r"|活动策划|展会筹备|客户拜访计划|团建方案",
    re.IGNORECASE,
)

# ── Multi-intent splitting via conjunction detection ────────────────────
# Split user messages at explicit conjunction words that signal independent intents.
# Only split when sub-clauses hit DIFFERENT business domains to avoid false positives.
_INTENT_SPLIT_RE = re.compile(
    r"[，,。；;]\s*(?:顺便|另外|还有|同时帮我|同时|再帮我|再|然后帮我|然后再|并且帮我|还想)"
    r"|(?:顺便|另外|还有|同时帮我|同时|再帮我|再帮|然后帮我|然后再|并且帮我|还想)",
)

# Domain keyword groups for cross-domain detection
_DOMAIN_KEYWORD_MAP: dict[str, set[str]] = {
    "crm": {"客户", "线索", "跟进", "商机", "联系人", "客户信息", "销售"},
    "approval": {"审批", "请假", "报销", "采购", "出差", "批准", "驳回"},
    "finance": {"财务", "报销", "付款", "发票", "费用", "预算"},
    "hr": {"考勤", "打卡", "请假", "入职", "离职", "薪资"},
    "project": {"项目", "任务", "进度", "里程碑", "排期"},
    "report": {"报表", "报告", "分析", "统计", "数据", "业绩", "销售额"},
    "contract": {"合同", "签约", "续约", "到期"},
}


def _detect_domain(text: str) -> set[str]:
    """Detect which business domains a text fragment touches."""
    domains = set()
    for domain, keywords in _DOMAIN_KEYWORD_MAP.items():
        if any(kw in text for kw in keywords):
            domains.add(domain)
    return domains


def detect_multi_intent(query: str) -> tuple[bool, list[str]]:
    """Detect if a query contains multiple independent intents across different domains.

    Returns:
        (is_multi_intent, list_of_sub_queries)
        If not multi-intent, returns (False, [query])
    """
    parts = _INTENT_SPLIT_RE.split(query)
    parts = [p.strip() for p in parts if p and p.strip()]

    if len(parts) < 2:
        return False, [query]

    # Check if sub-clauses hit different domains
    domains_per_part = [_detect_domain(p) for p in parts]
    all_domains = set()
    for d in domains_per_part:
        all_domains.update(d)

    # Only flag as multi-intent if at least 2 different domains are involved
    if len(all_domains) >= 2:
        # Verify at least 2 parts have non-overlapping domains
        for i in range(len(domains_per_part)):
            for j in range(i + 1, len(domains_per_part)):
                if domains_per_part[i] and domains_per_part[j] and not domains_per_part[i].intersection(domains_per_part[j]):
                    return True, parts

    return False, [query]
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

    # Check for multi-agent orchestration first (P1: COMPLEX or CRITICAL)
    needs_multi_agent = bool(_MULTI_AGENT_PATTERNS.search(text)) and complexity in (
        QueryComplexity.COMPLEX,
        QueryComplexity.CRITICAL,
    )

    # If multi-agent orchestration is needed, always route to director for WBS decomposition
    # The director will delegate to specific agents via the orchestrator
    if needs_multi_agent:
        return "director_agent", "task_decompose", True

    # Detect specific agent role for single-agent scenarios
    for pattern, agent_code, scene_code in _AGENT_ROLE_PATTERNS:
        if pattern.search(text):
            return agent_code, scene_code, False

    return "", "", False


def _filter_negated_keywords(text: str, keywords: set[str]) -> set[str]:
    """Remove keywords that are immediately preceded by a negation prefix.

    Uses both substring matching and jieba tokenization for more accurate
    Chinese keyword detection.

    E.g. text="不需要报销了", keywords={"报销"} → returns empty set
    because "不需要" negates "报销".
    """
    # Hybrid matching: substring + jieba tokens (case-insensitive for English keywords)
    tokens = _tokenize(text)
    text_lower = text.lower()
    tokens_lower = {t.lower() for t in tokens}
    matched = {
        kw for kw in keywords if kw.lower() in text_lower or kw.lower() in tokens_lower
    }
    if not matched:
        return matched
    # Check each matched keyword for negation prefix
    filtered = set()
    for kw in matched:
        idx = text.find(kw)
        if idx <= 0:
            filtered.add(kw)
            continue
        # Check if the text before the keyword ends with a negation prefix
        prefix = text[:idx]
        if _NEGATION_PREFIX_RE.search(prefix) and _NEGATION_PREFIX_RE.search(
            prefix
        ).end() == len(prefix):
            # Negated — skip this keyword
            continue
        filtered.add(kw)
    return filtered


# ─── Cheap Route Pre-check (Hermes-style heuristic) ───────────────────────
# Before entering expensive keyword scanning or LLM fallback, use message
# length and surface signals (code blocks, URLs, business keywords) to
# short-circuit obviously cheap queries with zero LLM cost.

_CODE_BLOCK_RE = re.compile(r"```")
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _try_cheap_route(text: str) -> tuple[QueryComplexity, str] | None:
    """Hermes-style conservative heuristic pre-check before LLM classification.

    Uses message length, word count, and surface-level signals (code blocks, URLs,
    business keywords) to short-circuit cheap queries without any LLM cost.

    Returns (complexity, intent_summary) if a cheap route is found, else None.
    """
    msg_len = len(text)
    words = len(text.split())
    has_code = bool(_CODE_BLOCK_RE.search(text))
    has_url = bool(_URL_RE.search(text))

    # Rule 1: Short, non-technical, non-business message -> SIMPLE
    # Guard: skip if the message matches realtime-info or longform-writing patterns,
    # which need their own dedicated classification paths downstream.
    if msg_len < 100 and not has_code and not has_url:
        # Check if the text contains ANY business keywords before allowing SIMPLE route.
        # This prevents "Customer Overview" (short but dense) from being short-circuited.
        biz_hits = _filter_negated_keywords(text, _ALL_BUSINESS_KEYWORDS)

        # P0 FIX: Explicitly block short intense business phrases from SIMPLE route
        # These are usually 2-6 chars: "查业绩", "客户概况", "项目详情"
        if (
            biz_hits
            or _REALTIME_INFO_PATTERNS.search(text)
            or _LONGFORM_WRITING_RE.search(text)
        ):
            logger.debug(
                "[Router] Business/Realtime intent detected in short message, bypassing SIMPLE cheap route"
            )
            return None

        # Truly trivial/short conversation
        if msg_len < 30:
            logger.info(
                "[Router] Cheap route: '%s' -> SIMPLE (len=%d, words=%d)",
                text[:30],
                msg_len,
                words,
            )
            return QueryComplexity.SIMPLE, "一般对话(快速路由)"

    # Rule 2: Medium-length, only MODERATE-level keywords -> MODERATE
    if msg_len < 200 and not has_code and not has_url:
        biz_hits = _filter_negated_keywords(text, _ALL_BUSINESS_KEYWORDS)
        if biz_hits:
            hits_critical = biz_hits.intersection(_CRITICAL_KEYWORDS)
            hits_complex = biz_hits.intersection(_COMPLEX_KEYWORDS)
            if not hits_critical and not hits_complex:
                logger.info(
                    "[Router] Cheap route: '%s' -> MODERATE (len=%d, words=%d)",
                    text[:30],
                    msg_len,
                    words,
                )
                return (
                    QueryComplexity.MODERATE,
                    f"工具查询(快速路由): {', '.join(biz_hits)}",
                )

    return None


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

    # 1c. Chitchat / casual conversation — no tools needed
    if _CHITCHAT_PATTERNS.search(text):
        return QueryComplexity.SIMPLE, "日常闲聊"

    # 1c2. Memory / recall queries — need memory context, MUST NOT be SIMPLE
    if _MEMORY_RECALL_PATTERNS.search(text):
        return QueryComplexity.MODERATE, "记忆回顾/历史对话查询"

    # 1c3. Cheap route pre-check — Hermes-style conservative heuristic.
    # Before expensive keyword scanning or LLM fallback, use message length
    # and surface signals to short-circuit obvious cheap queries.
    cheap = _try_cheap_route(text)
    if cheap is not None:
        return cheap

    # 1d. Long-form writing / content creation — MUST be checked BEFORE realtime
    #     info patterns, because queries like "写3000字推广软文" can accidentally
    #     match realtime patterns (e.g. "推" in "推荐") and get misclassified.
    if _LONGFORM_WRITING_RE.search(text):
        return QueryComplexity.COMPLEX, "长文写作/内容创作"

    # 1e. Real-time info queries — need web_search tool, NOT hallucination
    #     BUT: "查一下"/"帮我查" are too generic — if the message also contains
    #     business keywords (项目/客户/合同/线索 etc.), it's an internal data query,
    #     not a web search request.  Let it fall through to business keyword matching.
    if _REALTIME_INFO_PATTERNS.search(text):
        _biz_peek = _filter_negated_keywords(text, _ALL_BUSINESS_KEYWORDS)
        if not _biz_peek:
            return QueryComplexity.MODERATE, "需要联网搜索的实时信息"

    # Get all matched business keywords first to avoid missing lower tier keywords
    # when constructing the intent_summary, which is used for domain tool matching.
    matched_business = _filter_negated_keywords(text, _ALL_BUSINESS_KEYWORDS)
    if not matched_business and len(text) <= 200:
        # Short message with action intent verbs → upgrade to MODERATE for tool access
        if len(text) > 15 and any(
            v in text for v in ("帮我", "帮忙", "能不能", "可以", "怎么")
        ):
            return QueryComplexity.MODERATE, "一般对话"
        return QueryComplexity.SIMPLE, "一般对话"

    # 2. Critical (irreversible operations)
    matched_critical = matched_business.intersection(_CRITICAL_KEYWORDS)
    if matched_critical:
        # Semantic distinction: "查看审批" (query) vs "批准审批" (execute)
        # If only query verbs present and no execute verbs → downgrade to MODERATE
        has_query_verb = any(v in text for v in _QUERY_VERBS)
        has_execute_verb = any(v in text for v in _EXECUTE_VERBS)
        summary_str = ", ".join(matched_business)
        if has_query_verb and not has_execute_verb:
            return (
                QueryComplexity.MODERATE,
                f"查询操作(含敏感词但为只读): {summary_str}",
            )
        # No action verb at all → ambiguous, downgrade to MODERATE to avoid
        # over-triggering HITL / RAG for vague matches like "通知停水"
        if not has_query_verb and not has_execute_verb:
            return (
                QueryComplexity.MODERATE,
                f"业务相关(含敏感词但无明确动作): {summary_str}",
            )
        return QueryComplexity.CRITICAL, f"关键操作: {summary_str}"

    # 3. Complex (multi-step analysis)
    matched_complex = matched_business.intersection(_COMPLEX_KEYWORDS)
    if matched_complex or len(text) > 200:
        summary_str = ", ".join(matched_business) if matched_business else "长文本"
        return QueryComplexity.COMPLEX, f"复杂分析: {summary_str}"

    # 4. Moderate (single-tool operations)
    matched_moderate = matched_business.intersection(_MODERATE_KEYWORDS)
    if matched_moderate:
        return QueryComplexity.MODERATE, f"工具查询: {', '.join(matched_business)}"

    # 5. Check for any business indicator not covered above
    if matched_business:
        return QueryComplexity.MODERATE, f"业务相关: {', '.join(matched_business)}"

    # 6. No business context — general conversation, skip tools & RAG
    return QueryComplexity.SIMPLE, "一般对话"


# ─── RAG Relevance Gate ─────────────────────────────────────────────────────
# Only trigger RAG (embedding API call) when the query is likely to need
# information from uploaded documents / knowledge base.
# This prevents unnecessary text-embedding-3-small calls for queries like
# "帮我请假三天" or "查看客户列表" which use tools, not documents.

_RAG_TRIGGER_PATTERNS = re.compile(
    r"(文档|资料|手册|文件|知识库|规范|标准|参数|规格|说明书|"
    r"招标|投标|标书|方案|白皮书|技术文档|"
    r"产品.{0,4}(介绍|说明|参数|规格|对比)|"
    r"我们的.{0,4}(产品|方案|能力|优势)|"
    r"我方|公司.{0,4}(产品|方案|资质)|"
    r"根据.{0,6}(文件|文档|资料|要求)|"
    r"参考|查阅|检索|摘要|总结.{0,4}(文档|资料|文件)|"
    r"竞品|竞争.{0,4}(对手|分析|对比)|"
    r"行业.{0,4}(报告|分析|趋势)|"
    # Organizational / process knowledge queries
    r"谁负责|负责人是|归谁管|"
    r"流程是什么|怎么(申请|操作|办理|使用)|"
    r"怎么联系|联系方式|电话|邮箱|"
    r"(定义|标准|制度|规则|要求|政策|条例)是什么|"
    r"有(什么|哪些)(规定|制度|流程|要求))",
    re.IGNORECASE,
)


def _should_enable_rag(query: str) -> bool:
    """Check if a query likely needs RAG retrieval from knowledge base.

    Returns True only when the query suggests the user needs information
    from uploaded documents or company knowledge. This prevents unnecessary
    embedding API calls for general tool-based queries.
    """
    return bool(_RAG_TRIGGER_PATTERNS.search(query))


# ─── LLM-based Intent Classification ────────────────────────────────────────


async def _llm_classify_intent(
    query: str,
    config,
) -> tuple[QueryComplexity, str, list[str], bool]:
    """
    Use LLM for ambiguous query classification.

    Falls back to MODERATE if LLM fails.
    Returns: (complexity, intent_summary, domains, multi_intent)
    """
    from langchain_openai import ChatOpenAI

    prompt = f"""请分析以下用户输入，返回 JSON：
- complexity: simple(闲聊问候) / moderate(单一工具查询) / complex(多步骤分析) / critical(审批、金钱、敏感人事操作)
- reason: 一句话原因
- domains: 相关的业务域列表（可选值：oa_leave, attendance, approval, finance, project, crm, hr, asset, tender, analytics, knowledge, schedule, inventory, admin, vmd_content, vmd_market, calendar）
- multi_intent: 用户消息是否包含2个或以上独立的、不相关的操作意图（如"请假然后查业绩"包含请假和查询两个独立意图）

用户输入: {query}

返回示例: {{"complexity": "moderate", "reason": "查询客户信息", "domains": ["crm"], "multi_intent": false}}
"""

    try:
        # Resolve via LLM gateway
        resolved = None
        try:
            from app.services.llm_helpers import resolve_model_config

            org_id = getattr(config, "org_id", None) or "default"
            resolved = await resolve_model_config(org_id)
        except Exception:
            logger.debug(
                "LLM gateway model config unavailable in router, using default"
            )

        if resolved:
            llm = ChatOpenAI(
                model=resolved.get("model") or config.mini_model,
                api_key=resolved.get("api_key") or config.api_key,
                base_url=resolved.get("base_url") or config.base_url,
                temperature=0.0,
                timeout=10.0,
                callbacks=_get_langfuse_callbacks(
                    **_get_trace_context(config), tags=["router"]
                ),
            )
        else:
            llm = ChatOpenAI(
                model=config.mini_model,
                api_key=config.api_key,
                base_url=config.base_url,
                temperature=0.0,
                timeout=10.0,
                callbacks=_get_langfuse_callbacks(
                    **_get_trace_context(config), tags=["router"]
                ),
            )
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content or "{}"

        # Extract JSON from response
        json_match = re.search(r"\{[^}]+\}", content)
        if json_match:
            data = json.loads(json_match.group())
            complexity_str = data.get("complexity", "moderate")
            domains = data.get("domains", [])
            multi_intent = bool(data.get("multi_intent", False))
            if not isinstance(domains, list):
                domains = []
            if complexity_str in [c.value for c in QueryComplexity]:
                return (
                    QueryComplexity(complexity_str),
                    f"LLM 识别: {data.get('reason', '未知原因')}",
                    domains,
                    multi_intent,
                )
    except Exception as e:
        logger.error(f"[Router] LLM intent classification failed: {e}")

    return QueryComplexity.MODERATE, "一般业务查询 (LLM 分类失败)", [], False


# ─── Router Node ─────────────────────────────────────────────────────────────


# ─── Multi-turn continuation patterns ────────────────────────────────────────
# Short follow-up messages that should inherit the previous turn's complexity
# instead of being classified as SIMPLE "一般对话".
_CONTINUATION_PATTERNS = re.compile(
    r"^(好的|好|可以|行|嗯|对|是的|没错|继续|就这样|就这个|确认|同意|"
    r"ok|yes|sure|go ahead|proceed|"
    r"然后呢|还有呢|接下来|下一步|再看看|帮我看看|"
    r"对的|没问题|执行吧|开始吧|做吧)[。.！!？?～~\s]*$",
    re.IGNORECASE,
)


async def route_node(state: AgentState) -> dict:
    """
    LangGraph node: Classify user intent and pick the optimal model.
    """
    config = state["config"]
    messages = state.get("messages", [])

    # P0-2: Inject goal context at conversation start
    if hasattr(config, "user_id") and config.user_id:
        try:
            from app.agent.goal_tracker import goal_tracker

            goal_context = await goal_tracker.get_goal_context_for_agent(
                config.user_id, getattr(config, "org_id", "default")
            )
            if goal_context:
                from langchain_core.messages import SystemMessage

                messages.insert(0, SystemMessage(content=goal_context))
        except Exception as e:
            logger.debug(f"Goal context injection skipped: {e}")

    # Load DB keyword rules on first invocation (cached after first call)
    await _load_db_intent_rules()

    # Extract last user message
    last_user_msg = ""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            last_user_msg = msg.content
            break
        elif isinstance(msg, dict) and msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    # P1 #7: Reuse early classification from stream.py if available (avoids re-calling classify_query)
    _early_complexity = state.get("complexity")
    _early_intent = state.get("intent_summary", "")
    if (
        _early_complexity is not None
        and isinstance(_early_complexity, QueryComplexity)
        and _early_intent
        and _early_intent != "一般对话"
    ):
        complexity = _early_complexity
        intent_summary = _early_intent
        logger.info(
            f"[Router] Reusing early classification: {complexity.value} ({intent_summary})"
        )
    else:
        complexity, intent_summary = classify_query(last_user_msg)

    # ── Cost-aware routing log ──
    _routed_model = config.get_model_for_complexity(complexity)
    logger.info(
        f"[Router] '{last_user_msg[:30]}' → {complexity.value} "
        f"(model={_routed_model}, "
        f"tier={complexity.model_tier})"
    )

    # ── Multi-turn context: inherit previous complexity for follow-up messages ──
    # If the current message is a short continuation ("好的"/"继续"/"就这样"),
    # keep the previous turn's complexity instead of falling to SIMPLE.
    prev_complexity = state.get("complexity")
    if (
        complexity == QueryComplexity.SIMPLE
        and intent_summary in ("简单问候或闲聊", "一般对话")
        and prev_complexity is not None
        and prev_complexity != QueryComplexity.SIMPLE
        and _CONTINUATION_PATTERNS.match(last_user_msg.strip())
    ):
        complexity = prev_complexity
        intent_summary = f"多轮延续(继承上轮 {complexity.value})"
        logger.info(
            f"[Router] Multi-turn continuation detected, inheriting complexity={complexity.value}"
        )

    # LLM fallback: only for genuinely ambiguous queries that passed all keyword checks.
    # Skip LLM classification when:
    # - Message is short (≤10 chars) — unlikely to be complex business query
    # This saves ~500ms per SIMPLE query by avoiding an extra LLM round-trip.
    intent_domains: list[str] = []
    multi_intent = False

    # Pre-check: conjunction-based multi-intent detection (fast, no LLM)
    _mi_detected, _mi_parts = detect_multi_intent(last_user_msg)
    if _mi_detected:
        multi_intent = True
        logger.info(
            f"[Router] Multi-intent detected via conjunction split: {len(_mi_parts)} parts"
        )

    if intent_summary == "一般对话" and len(last_user_msg.strip()) > 10:
        # Fast path: semantic router (embedding similarity, ~50ms)
        try:
            from app.agent.semantic_router import semantic_router

            sr_intent, sr_conf, sr_domains = await semantic_router.classify(
                last_user_msg,
                org_id=config.org_id if hasattr(config, "org_id") else None,
            )
            if sr_intent and sr_conf > 0.85:
                complexity_str = semantic_router.get_complexity(sr_intent)
                complexity = QueryComplexity(complexity_str)
                intent_summary = sr_intent
                intent_domains = sr_domains
                logger.info(
                    f"[Router] Semantic router hit: {sr_intent} (conf={sr_conf:.3f}), skipping LLM classify"
                )
            else:
                # Slow path: LLM classify
                complexity, intent_summary, intent_domains, multi_intent = (
                    await _llm_classify_intent(last_user_msg, config)
                )
        except Exception:
            logger.error(
                "[Router] Semantic router failed, falling back to LLM", exc_info=True
            )
            complexity, intent_summary, intent_domains, multi_intent = (
                await _llm_classify_intent(last_user_msg, config)
            )

    selected_model = config.get_model_for_complexity(complexity)

    # ── VMD Agent Role Detection (additive) ──
    agent_code, scene_code, needs_multi_agent = detect_agent_role(
        last_user_msg, complexity
    )

    # P1: Multi-intent detection — if LLM detected multiple independent intents,
    # escalate to WBS decomposition even without pattern match
    if (
        not needs_multi_agent
        and multi_intent
        and complexity
        in (QueryComplexity.MODERATE, QueryComplexity.COMPLEX, QueryComplexity.CRITICAL)
    ):
        agent_code, scene_code, needs_multi_agent = (
            "director_agent",
            "task_decompose",
            True,
        )
        logger.info(
            "[Router] Multi-intent detected by LLM, escalating to WBS decomposition"
        )

    if agent_code:
        logger.info(
            f"[Router] VMD role detected: agent_code={agent_code} scene={scene_code} multi_agent={needs_multi_agent}"
        )

    logger.info(
        f"[Router] user={config.user_id} complexity={complexity.value} model={selected_model} intent='{intent_summary}'"
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
        "intent_domains": intent_domains,
        "current_phase": AgentPhase.PLANNING,
        "thinking_steps": [thinking_step],
    }

    # Write VMD role info into state (only if detected)
    if agent_code:
        result["agent_code"] = agent_code
        result["scene_code"] = scene_code

    # P1-7: Check for workflow recipes using regex
    try:
        import re

        from app.agent.workflow_recipes import RECIPES

        matched_recipe = None

        contract_approval_pattern = re.compile(
            r"(提交|发起|申请).*(合同|协议).*(审批|核准)|(合同|协议).*(提交|发起|申请).*(审批|核准)"
        )
        onboard_pattern = re.compile(r"(办理|给|为|新).*(入职|报到)")

        if contract_approval_pattern.search(last_user_msg):
            matched_recipe = "submit_contract_approval"
        elif onboard_pattern.search(last_user_msg):
            matched_recipe = "onboard_employee"

        if matched_recipe and matched_recipe in RECIPES:
            # Check if it's a pydantic model or dataclass
            recipe = RECIPES[matched_recipe]
            if hasattr(recipe, "model_dump"):
                result["workflow_recipe"] = recipe.model_dump()
            elif hasattr(recipe, "dict"):
                result["workflow_recipe"] = recipe.dict()
            else:
                result["workflow_recipe"] = vars(recipe)
            logger.info(
                f"[Router] Matched workflow recipe: {matched_recipe} for query '{last_user_msg}'"
            )
    except Exception as e:
        logger.debug(f"[Router] Workflow recipe matching skipped: {e}")

    return result
