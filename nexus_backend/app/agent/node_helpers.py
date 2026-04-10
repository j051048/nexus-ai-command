"""
Shared imports, helpers, constants and Pydantic models for graph nodes.

All node modules import from here to avoid circular dependencies.
"""

import asyncio
import logging
import re
import time

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.agent.state import (
    AgentConfig,
    AgentPhase,  # noqa: F401
    AgentState,  # noqa: F401
    QueryComplexity,  # noqa: F401
    ThinkingStep,  # noqa: F401
    ToolCallRecord,  # noqa: F401
)
from app.core.ai_metrics import (
    check_tool_alert,  # noqa: F401
    record_hallucination,  # noqa: F401
    record_llm_latency,  # noqa: F401
    record_tool_execution,  # noqa: F401
)
from app.services.content_moderation import sanitize_output, scan_content  # noqa: F401
from app.services.error_recovery_service import (
    llm_circuit_breaker,
    tool_circuit_breaker,
)  # noqa: F401
from app.services.plugin_system_service import (
    ExtensionPoint,
    plugin_system_service,
)  # noqa: F401
from app.tools import get_all_tools_schema, get_tool

logger = logging.getLogger(__name__)

# ── Prompt injection sanitization ──────────────────────────────────────────

# Patterns that look like prompt-injection attempts in user-derived strings
_INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(previous|above|all)\s+instructions"
    r"|you\s+are\s+now"
    r"|system\s*:\s*"
    r"|<\|im_start\|>"
    r"|<\|im_end\|>"
    r"|```\s*(system|assistant)"
    r"|IMPORTANT\s*:"
    r"|OVERRIDE\s*:"
    r"|忽略(以上|之前|所有)(指令|规则|提示)"
    r"|你现在是"
    r"|新的?指令"
    r"|请?无视(以上|之前))",
    re.IGNORECASE,
)


def sanitize_prompt_field(value: str, max_len: int = 500) -> str:
    """Sanitize a user-derived string before injecting it into an LLM prompt.

    - Strips known prompt-injection patterns
    - Truncates to max_len to prevent context stuffing
    - Removes control characters
    """
    if not value:
        return value
    # Remove control chars (keep newlines/tabs)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    # Strip injection patterns
    cleaned = _INJECTION_PATTERNS.sub("[FILTERED]", cleaned)
    # Truncate
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len] + "..."
    return cleaned.strip()


# Long-running tools that need extended timeout (120s instead of default 30s)
# Canonical definition — also used by nodes_orchestrator.py
LONG_RUNNING_TOOLS: set[str] = {
    "generate_product_manual",
    "generate_faq_response",
    "generate_training_material",
    "generate_weekly_report",
    "generate_competitor_analysis",
    "generate_tender_analysis",
    "generate_contract_summary",
    "generate_social_post",
    "generate_whitepaper",
    "generate_application_note",
    "batch_analyze_documents",
    "query_knowledge_base",
    "strategy_simulation",
    "get_company_stats",
    "llm_task",
    # Previously only in nodes_orchestrator.py — now unified
    "generate_bid_document",
    "analyze_contract",
    "generate_market_research",
}

# Subset of LONG_RUNNING_TOOLS that should be offloaded to Celery workers
# when available, for independent failure isolation and process-level timeout.
CELERY_ISOLATED_TOOLS: set[str] = {
    "generate_product_manual",
    "generate_whitepaper",
    "generate_bid_document",
    "strategy_simulation",
    "batch_analyze_documents",
    "generate_market_research",
}


# ─── Pydantic models for structured LLM output in reflect_node ───────────────


class GroundednessCheck(BaseModel):
    """RAG groundedness evaluation result."""

    is_grounded: bool = Field(
        description="Whether the response is grounded in reference knowledge"
    )
    reason: str = Field(default="", description="Reason for the evaluation")
    score: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Groundedness score 0-1"
    )


class HallucinationCheck(BaseModel):
    """LLM-based hallucination detection result."""

    is_hallucination: bool = Field(
        description="Whether the response contains fabricated information"
    )
    reason: str = Field(default="", description="Reason for the evaluation")
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Confidence score 0-1"
    )


class CriticResult(BaseModel):
    """P1-5: Independent critic evaluation of agent response quality."""

    completeness: float = Field(
        default=0.5, ge=0.0, le=1.0, description="回答是否完整覆盖用户问题"
    )
    relevance: float = Field(
        default=0.5, ge=0.0, le=1.0, description="回答与用户意图的相关性"
    )
    accuracy: float = Field(
        default=0.5, ge=0.0, le=1.0, description="信息准确性（基于工具结果）"
    )
    passed: bool = Field(default=True, description="是否通过评审")
    improvement_suggestion: str = Field(
        default="", description="改进建议（未通过时提供）"
    )


# ─── Agent Lifecycle Hooks (inspired by OpenClaw agent-hooks.ts) ──────────────
# Lightweight interceptor system for: before_tool_call, after_tool_call,
# before_prompt_build. Hooks can modify args, log telemetry, or block execution.

from collections.abc import Callable

# Hook type: async (context_dict) -> context_dict | None
# Return None to signal "block this action"
_hooks: dict[str, list[Callable]] = {
    "before_tool_call": [],
    "after_tool_call": [],
    "before_prompt_build": [],
}


async def run_hooks(event: str, context: dict) -> dict | None:
    """Run all hooks for an event in registration order.

    Returns the (possibly modified) context dict, or None if any hook blocked.
    Hooks are async-safe: sync hooks are also supported.
    """
    import asyncio as _asyncio

    for hook in _hooks.get(event, []):
        try:
            if _asyncio.iscoroutinefunction(hook):
                result = await hook(context)
            else:
                result = hook(context)
            if result is None:
                logger.info(f"[Hook] {event} blocked by {hook.__name__}")
                return None
            context = result
        except Exception as e:
            logger.warning(f"[Hook] {event} hook {hook.__name__} raised: {e}")
            # Hooks should not crash the pipeline — log and continue
    return context


# P1 Fix: Cache tool schemas to avoid rebuilding on every request
_tool_schemas_cache = None
_tool_schemas_count = None

# Role hierarchy for tool access filtering
_ROLE_HIERARCHY = {
    "guest": 0,
    "employee": 1,
    "manager": 2,
    "admin": 3,
    "boss": 3,
    "founder": 4,
}

# ─── Intent-based tool filtering (P2: reduce token payload) ──────────────

# Always included regardless of intent (core infrastructure tools only)
# NOTE: web_search is NOT included here — it's conditionally added via
# DataPrimacyGuard to prevent "OpenClaw syndrome" (asking the web when
# internal data should be queried from Supabase).
_ALWAYS_INCLUDE_TOOLS: set[str] = {
    "ask_user",
    "compact_context",
    "llm_task",
    "save_memory",
}

# Domains where web search IS appropriate (non-enterprise-private data)
_WEB_SEARCH_ALLOWED_DOMAINS: set[str] = {
    "knowledge",
    "tender",
    "analytics",
    "vmd_market",
}

# Keywords in intent_summary that signal user explicitly wants web search
_WEB_SEARCH_INTENT_KEYWORDS: set[str] = {
    "搜索",
    "查一下",
    "网上",
    "搜一下",
    "百度",
    "谷歌",
    "google",
    "最新",
    "新闻",
    "行业",
    "趋势",
    "市场",
}

# ─── Scene-based Tool Policy (inspired by OpenClaw tool-policy-pipeline) ────
# Per-scene allow/deny overrides. If a scene_code is listed here, ONLY
# the allowed tools (+ always-include) are available. Deny lists are applied
# after allow lists. This prevents agents from calling irrelevant tools.

_SCENE_TOOL_POLICY: dict[str, dict] = {
    # Leave/OA scenes: restrict to OA-related tools only
    "leave_request": {
        "allow_domains": ["oa_leave", "oa_task", "attendance", "schedule"],
    },
    "attendance_check": {
        "allow_domains": ["attendance", "oa_leave"],
    },
    # CRM scenes: focus on customer-facing tools
    "crm_followup": {
        "allow_domains": ["crm", "knowledge", "analytics", "vmd_content"],
    },
    "sales_pipeline": {
        "allow_domains": ["crm", "analytics", "finance"],
    },
    # Tender/bid scenes: focus on competitive analysis
    "tender_analysis": {
        "allow_domains": ["tender", "knowledge", "analytics", "crm"],
    },
    "proposal": {
        "allow_domains": ["tender", "knowledge", "analytics", "crm"],
    },
    # Finance scenes
    "expense_claim": {
        "allow_domains": ["finance", "approval"],
    },
    # Content generation scenes: broad creative access
    "content_generation": {
        "allow_domains": ["vmd_content", "vmd_market", "knowledge", "crm"],
    },
    # Admin scenes: restricted to admin tools
    "system_admin": {
        "allow_domains": ["admin", "hr", "asset"],
        "deny_tools": {"create_leave_request", "create_expense_claim"},
    },
    # Task decomposition: needs all tools for sub-agent dispatch
    "task_decompose": {
        # No restrictions — full access for orchestration
    },
}

# Domain → tool name sets
_DOMAIN_TOOL_MAP: dict[str, set[str]] = {
    "oa_leave": {
        "create_leave_request",
        "query_leave_status",
        "request_leave",
        "book_meeting",
        "create_work_handover",
        "generate_onboarding_checklist",
        "submit_approval_on_behalf",
    },
    "oa_task": {
        "assign_task",
        "send_notification",
        "book_meeting",
        "create_work_handover",
        "publish_announcement",
    },
    "attendance": {
        "clock_in_out",
        "get_attendance_record",
        "attendance_statistics",
        "create_shift_schedule",
        "list_shift_schedules",
        "request_leave",
        "query_attendance",
        "query_team_attendance",
    },
    "approval": {
        "approve_request",
        "reject_request",
        "get_pending_approvals",
        "submit_approval_on_behalf",
        "get_employee_approval_history",
        "smart_approve",
        "list_approval_flows",
        "create_approval_flow",
        "approve_expense",
    },
    "finance": {
        "create_expense_claim",
        "query_expense_status",
        "query_budget",
        "query_salary",
        "recognize_invoice",
        "submit_expense",
        "list_expenses",
        "approve_expense",
        "check_budget",
    },
    "project": {
        "get_projects",
        "create_project",
        "create_project_event",
        "generate_weekly_report",
        "assign_task",
        "list_work_orders",
        "create_work_order",
        "get_work_order_detail",
        "update_work_order",
        "work_order_statistics",
    },
    "crm": {
        "get_customers",
        "get_customer_detail",
        "create_customer",
        "update_customer",
        "add_follow_up",
        "get_follow_ups",
        "update_customer_stage",
        "get_sales_pipeline",
        "get_contracts",
        "create_contract",
        "get_expiring_contracts",
        "analyze_contract",
        "generate_customer_profile",
    },
    "hr": {
        "get_employee_profile",
        "get_employee_detail",
        "get_employee_info",
        "list_employees",
        "create_employee",
        "update_employee",
        "create_performance_review",
        "manage_recruitment",
        "list_departments",
        "create_department",
        "update_department",
        "org_statistics",
    },
    "asset": {
        "list_assets",
        "get_asset_detail",
        "create_asset",
        "update_asset",
        "transfer_asset",
        "asset_statistics",
    },
    "tender": {
        "analyze_tender_document",
        "get_battlecard",
        "list_competitors",
        "search_bidding_projects",
        "generate_bid_document",
        "generate_deviation_table",
        "check_bid_compliance",
        "extract_bid_requirements",
    },
    "analytics": {
        "get_performance_report",
        "get_company_stats",
        "smart_report",
        "anomaly_detection",
        "get_business_dashboard",
        "get_team_insight",
        "analyze_data_attribution",
        "strategy_simulation",
    },
    "knowledge": {
        "query_knowledge_base",
        "batch_analyze_documents",
        "load_knowledge",
    },
    "schedule": {
        "create_scheduled_task",
        "list_scheduled_tasks",
        "delete_scheduled_task",
        "get_daily_briefing",
        "get_pending_approvals",
        "assign_task",
        "create_task",
        "update_task",
        "list_tasks",
        "get_user_preferences",
        "update_user_preferences",
    },
    "vmd_content": {
        "generate_product_manual",
        "generate_whitepaper",
        "generate_application_note",
        "generate_social_post",
        "generate_sales_script",
        "generate_competitor_comparison",
        "generate_training_material",
        "generate_quotation_template",
    },
    "vmd_market": {
        "monitor_industry_trends",
        "generate_market_research",
        "generate_competitor_analysis",
        "aggregate_customer_feedback",
        "generate_maintenance_reminder",
        "generate_faq_response",
        "generate_repurchase_campaign",
        "customer_lifecycle_analysis",
    },
    "admin": {
        "list_system_configs",
        "update_system_config",
        "list_certificates",
        "create_certificate",
        "expiring_certificates",
        "renew_certificate",
        "process_onboarding",
        "process_resignation",
        "process_asset_lifecycle",
        "publish_announcement",
        "query_audit_logs",
    },
    "inventory": {
        "list_inventory",
        "inventory_in",
        "inventory_out",
        "inventory_statistics",
    },
}

# Keyword → domain(s) mapping — reuses router.py keyword vocabulary
_KEYWORD_DOMAIN_MAP: dict[str, list[str]] = {
    # OA / Leave
    "请假": ["oa_leave"],
    "出差": ["oa_leave", "approval"],
    "会议": ["oa_leave"],
    "日程": ["oa_leave", "schedule"],
    "交接": ["oa_leave"],
    "调休": ["oa_leave", "attendance"],
    "年假": ["oa_leave"],
    "提醒": ["oa_task", "oa_leave", "schedule"],
    # OA Task / Administrative
    "安排": ["oa_task", "project"],
    "去办": ["oa_task"],
    "跑腿": ["oa_task"],
    "行政": ["oa_task", "admin"],
    "送资料": ["oa_task"],
    "取文件": ["oa_task"],
    "交付": ["oa_task", "project"],
    "派人": ["oa_task", "project"],
    "吩咐": ["oa_task"],
    "交代": ["oa_task"],
    # Attendance
    "考勤": ["attendance"],
    "打卡": ["attendance"],
    "补卡": ["attendance"],
    "加班": ["attendance"],
    "排班": ["attendance"],
    # Approval
    "审批": ["approval"],
    "批准": ["approval"],
    "拒绝": ["approval"],
    "驳回": ["approval"],
    "批了": ["approval"],
    "不批": ["approval"],
    "同意": ["approval"],
    "通过": ["approval"],
    "申请": ["approval"],
    # Finance
    "报销": ["finance"],
    "预算": ["finance"],
    "工资": ["finance"],
    "薪资": ["finance"],
    "发票": ["finance"],
    "开票": ["finance"],
    "付款": ["finance"],
    "转账": ["finance"],
    "发工资": ["finance"],
    "费用": ["finance"],
    "收入": ["finance", "analytics"],
    # Project
    "项目": ["project"],
    "进度": ["project"],
    "任务": ["project", "schedule"],
    "工单": ["project"],
    "维修": ["project", "asset"],
    "派工": ["project"],
    # CRM / Sales
    "客户": ["crm"],
    "合同": ["crm"],
    "商机": ["crm"],
    "线索": ["crm"],
    "跟进": ["crm"],
    "漏斗": ["crm"],
    "转化率": ["crm", "analytics"],
    "跟进率": ["crm", "analytics"],
    # HR
    "员工": ["hr"],
    "通讯录": ["hr"],
    "培训": ["hr"],
    "招聘": ["hr"],
    "绩效": ["hr", "analytics"],
    "部门": ["hr"],
    "入职": ["hr", "admin"],
    "离职": ["hr", "admin"],
    "组织架构": ["hr"],
    "人事": ["hr"],
    # Asset
    "设备": ["asset"],
    "资产": ["asset"],
    "车辆": ["asset"],
    "快递": ["asset"],
    "印章": ["asset"],
    # Tender / Bidding
    "招标": ["tender"],
    "投标": ["tender"],
    "招投标": ["tender"],
    "标书": ["tender"],
    "竞品": ["tender", "vmd_content"],
    "battlecard": ["tender"],
    # Analytics
    "分析": ["analytics"],
    "报告": ["analytics"],
    "统计": ["analytics"],
    "趋势": ["analytics", "vmd_market"],
    "预测": ["analytics"],
    "仪表盘": ["analytics"],
    "dashboard": ["analytics"],
    "总结": ["analytics"],
    "经营": ["analytics"],
    # Schedule
    "待办": ["schedule", "approval"],
    "日报": ["schedule"],
    "周报": ["project"],
    "简报": ["schedule", "analytics"],
    "定时": ["schedule"],
    "偏好": ["schedule"],
    "设置": ["schedule"],
    "通知设置": ["schedule"],
    # VMD
    "白皮书": ["vmd_content", "knowledge"],
    "文案": ["vmd_content", "knowledge"],
    "话术": ["vmd_content", "knowledge"],
    "手册": ["vmd_content", "knowledge"],
    "软文": ["vmd_content", "knowledge"],
    "推广文": ["vmd_content", "knowledge"],
    "长文": ["vmd_content", "knowledge"],
    "文章": ["vmd_content", "knowledge"],
    "写作": ["vmd_content", "knowledge"],
    "内容创作": ["vmd_content", "knowledge"],
    "策划案": ["vmd_content", "knowledge"],
    "方案书": ["vmd_content", "knowledge"],
    "市场": ["vmd_market"],
    "舆情": ["vmd_market"],
    # Admin
    "证照": ["admin"],
    "盖章": ["admin"],
    "用印": ["admin"],
    "签署": ["admin"],
    "公告": ["admin", "approval"],
    "通知": ["oa_task", "approval", "admin"],
    "全员": ["admin", "oa_task"],
    "全体": ["admin", "oa_task"],
    "放假": ["admin", "oa_task"],
    "公告通知": ["admin", "oa_task"],
    "审计": ["admin"],
    "审计日志": ["admin"],
    "安全审计": ["admin"],
    "异常登录": ["admin"],
    "数据导出": ["admin"],
    # Knowledge
    "知识库": ["knowledge"],
    "搜索": ["knowledge"],
    "文档": ["knowledge", "vmd_content"],
    "RAG": ["knowledge"],
    "产品": ["knowledge", "crm", "vmd_content"],
    # Inventory
    "库存": ["inventory"],
    "出库": ["inventory"],
    "入库": ["inventory"],
    # General high-frequency
    "查询": ["analytics", "knowledge"],
    "怎么样": ["analytics"],
}


def _resolve_domains_from_intent(intent_summary: str) -> set[str]:
    """Extract tool domains from router's intent_summary string.

    intent_summary format examples:
      - "工具查询: 请假, 考勤"
      - "关键操作: 批准, 审批"
      - "复杂分析: 分析, 报告"
      - "一般业务查询"
    """
    domains: set[str] = set()
    for keyword, domain_list in _KEYWORD_DOMAIN_MAP.items():
        if keyword in intent_summary:
            domains.update(domain_list)
    return domains


# ── Auto-sync tool domains from BaseTool.domain attribute ───────────────────
_domains_synced = False


def _sync_tool_domains():
    """Populate _DOMAIN_TOOL_MAP from tool.domain attributes (additive).

    Called once on first _get_tool_schemas() invocation.  Tools that declare
    a ``domain`` property are automatically added to the corresponding domain
    set, so new tools only need to set ``domain = "finance"`` instead of
    manually editing _DOMAIN_TOOL_MAP.

    S4 Enhancement: Also auto-maps tools based on ToolInfo.category as fallback,
    ensuring tools without explicit domain property still participate in
    intent-based filtering.
    """
    global _domains_synced
    if _domains_synced:
        return
    _domains_synced = True

    from app.tools import TOOL_REGISTRY, _load_all
    from app.tools.registry import get_tool_info

    _load_all()
    _auto_mapped = 0
    for name, tool in TOOL_REGISTRY.items():
        domain = getattr(tool, "domain", None)
        if not domain:
            # S4: Fallback to ToolInfo.category for domain mapping
            info = get_tool_info(name)
            if info and info.category and info.category != "general":
                domain = info.category
            else:
                continue
            _auto_mapped += 1
        if domain in _DOMAIN_TOOL_MAP:
            _DOMAIN_TOOL_MAP[domain].add(name)
        else:
            _DOMAIN_TOOL_MAP[domain] = {name}
    if _auto_mapped:
        logger.debug(
            f"[ToolDomainSync] Auto-mapped {_auto_mapped} tools from ToolInfo.category"
        )


def _get_tool_schemas(
    user_role: str | None = None,
    intent_summary: str | None = None,
    scene_code: str | None = None,
    intent_domains: list[str] | None = None,
):
    """Get tool schemas with multi-layer filtering pipeline.

    Filter layers (applied in order):
      1) User role (RBAC) — exclude tools above user's permission level
      2) Scene policy — allow/deny overrides per business scene
      3) Intent domain — Router LLM domains preferred, fallback to keyword matching
    """
    global _tool_schemas_cache, _tool_schemas_count
    _sync_tool_domains()
    if _tool_schemas_cache is None:
        schemas = get_all_tools_schema()
        _tool_schemas_cache = schemas
        _tool_schemas_count = len(schemas)

    if not user_role:
        filtered = list(_tool_schemas_cache)
    else:
        # Layer 1: Filter schemas by user role — exclude tools the user cannot execute
        user_level = _ROLE_HIERARCHY.get(user_role, 1)
        filtered = []
        for schema in _tool_schemas_cache:
            tool_name = schema.get("function", {}).get("name", "")
            tool = get_tool(tool_name)
            if not tool:
                continue
            req_role = getattr(tool, "required_role", "all")
            if req_role in ("all", "ai_assistant"):
                filtered.append(schema)
            else:
                req_level = _ROLE_HIERARCHY.get(req_role, 1)
                if user_level >= req_level:
                    filtered.append(schema)

    # Layer 2: Scene-based policy — allow/deny per scene_code
    if scene_code and scene_code in _SCENE_TOOL_POLICY:
        policy = _SCENE_TOOL_POLICY[scene_code]
        allow_domains = policy.get("allow_domains")
        deny_tools = policy.get("deny_tools", set())

        if allow_domains:
            allowed_tools = _ALWAYS_INCLUDE_TOOLS.copy()
            for d in allow_domains:
                allowed_tools |= _DOMAIN_TOOL_MAP.get(d, set())
            before_count = len(filtered)
            filtered = [s for s in filtered if s["function"]["name"] in allowed_tools]
            logger.debug(
                f"[ToolPolicy] Scene '{scene_code}' allow_domains={allow_domains} "
                f"→ {len(filtered)} tools (from {before_count})"
            )

        if deny_tools:
            filtered = [s for s in filtered if s["function"]["name"] not in deny_tools]
            logger.debug(
                f"[ToolPolicy] Scene '{scene_code}' denied {len(deny_tools)} tools"
            )

    # Layer 3: Intent-based filtering — Router LLM domains preferred, then keyword match
    if intent_domains:
        # Router LLM has explicitly identified business domains
        relevant_tools = _ALWAYS_INCLUDE_TOOLS.copy()
        for d in intent_domains:
            relevant_tools |= _DOMAIN_TOOL_MAP.get(d, set())
        before_count = len(filtered)
        filtered = [s for s in filtered if s["function"]["name"] in relevant_tools]
        logger.debug(
            f"[ToolFilter] Router LLM domains={intent_domains} "
            f"→ {len(filtered)} tools (from {before_count})"
        )
    elif intent_summary:
        domains = _resolve_domains_from_intent(intent_summary)
        if domains:
            relevant_tools = _ALWAYS_INCLUDE_TOOLS.copy()
            for d in domains:
                relevant_tools |= _DOMAIN_TOOL_MAP.get(d, set())
            before_count = len(filtered)
            filtered = [s for s in filtered if s["function"]["name"] in relevant_tools]
            logger.debug(
                f"[ToolFilter] Intent '{intent_summary}' → domains={domains} "
                f"→ {len(filtered)} tools (from {before_count})"
            )
        elif not scene_code:
            # Fallback: no keyword match + no scene policy → use high-frequency domains
            _FALLBACK_DOMAINS = [
                "oa_leave",
                "crm",
                "approval",
                "finance",
                "hr",
                "analytics",
                "knowledge",
                "tender",
            ]
            relevant_tools = _ALWAYS_INCLUDE_TOOLS.copy()
            for d in _FALLBACK_DOMAINS:
                relevant_tools |= _DOMAIN_TOOL_MAP.get(d, set())
            before_count = len(filtered)
            filtered = [s for s in filtered if s["function"]["name"] in relevant_tools]
            logger.debug(
                f"[ToolFilter] No domain match for '{intent_summary}', "
                f"fallback → {len(filtered)} tools (from {before_count})"
            )

    # DataPrimacyGuard: conditionally inject web_search only when appropriate
    # Prevents "OpenClaw syndrome" — querying the web for internal enterprise data
    _should_allow_web_search = False
    if intent_domains:
        _should_allow_web_search = bool(
            set(intent_domains) & _WEB_SEARCH_ALLOWED_DOMAINS
        )
    if not _should_allow_web_search and intent_summary:
        _should_allow_web_search = any(
            kw in intent_summary for kw in _WEB_SEARCH_INTENT_KEYWORDS
        )
    if not _should_allow_web_search and not intent_domains and not intent_summary:
        # No routing info at all (e.g., SIMPLE queries) — allow web search as fallback
        _should_allow_web_search = True

    if _should_allow_web_search:
        # Add web_search schema if not already present
        ws_schema = next(
            (
                s
                for s in (_tool_schemas_cache or [])
                if s["function"]["name"] == "web_search"
            ),
            None,
        )
        if ws_schema and not any(
            s["function"]["name"] == "web_search" for s in filtered
        ):
            filtered.append(ws_schema)
    else:
        # Explicitly remove web_search from filtered results
        filtered = [s for s in filtered if s["function"]["name"] != "web_search"]
        if intent_domains:
            logger.debug(
                f"[DataPrimacy] web_search blocked: domains={intent_domains} are enterprise-internal"
            )

    # Safety cap: if filtering still leaves too many tools, keep only the most relevant
    MAX_TOOLS = 30
    if len(filtered) > MAX_TOOLS:
        logger.info(
            f"[ToolFilter] Capping {len(filtered)} tools to {MAX_TOOLS} (always-include + domain-sorted)"
        )
        # Prioritize always-include tools, then domain-matched, then the rest
        always = [s for s in filtered if s["function"]["name"] in _ALWAYS_INCLUDE_TOOLS]
        rest = [
            s for s in filtered if s["function"]["name"] not in _ALWAYS_INCLUDE_TOOLS
        ]
        filtered = (always + rest)[:MAX_TOOLS]

    return filtered


# ─── Helpers ─────────────────────────────────────────────────────────────────


# Cached Langfuse client to avoid recreating HTTP connections per callback
_langfuse_client = None


def _get_langfuse_callbacks(
    *,
    trace_id: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    tags: list[str] | None = None,
) -> list | None:
    """Return Langfuse CallbackHandler list if enabled, else None.

    Shared across all LLM construction sites to ensure complete observability.
    Respects LANGFUSE_SAMPLE_RATE for production cost control.
    When trace_id is provided, all LLM spans are grouped under the same trace.
    Reuses a cached Langfuse client to avoid per-call HTTP client creation.
    """
    global _langfuse_client
    try:
        from app.core.config import settings

        if settings.LANGFUSE_ENABLED:
            import random

            if random.random() > settings.LANGFUSE_SAMPLE_RATE:
                return None
            from langfuse.callback import CallbackHandler as LangfuseCallbackHandler

            # Reuse cached Langfuse client for HTTP connection pooling
            if _langfuse_client is None:
                from langfuse import Langfuse

                _langfuse_client = Langfuse(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_HOST,
                )

            kwargs: dict = {"langfuse_client": _langfuse_client}
            if trace_id:
                kwargs["trace_id"] = trace_id
            if session_id:
                kwargs["session_id"] = session_id
            if user_id:
                kwargs["user_id"] = user_id
            if tags:
                kwargs["tags"] = tags
            return [LangfuseCallbackHandler(**kwargs)]
    except Exception:
        pass
    return None


def _get_trace_context(
    config: AgentConfig | None = None,
    configurable: dict | None = None,
) -> dict:
    """Extract Langfuse trace context from configurable's trace_logger.

    Returns kwargs suitable for passing to _get_langfuse_callbacks(**ctx).
    """
    ctx: dict = {}
    trace_logger = (configurable or {}).get("trace_logger")
    if trace_logger and hasattr(trace_logger, "trace_id"):
        ctx["trace_id"] = trace_logger.trace_id
        sid = getattr(trace_logger, "session_id", None)
        if sid:
            ctx["session_id"] = sid
        uid = getattr(trace_logger, "user_id", None)
        if uid:
            ctx["user_id"] = uid
    elif config:
        if config.user_id:
            ctx["user_id"] = config.user_id
    return ctx


def _get_llm(
    config: AgentConfig,
    model: str | None = None,
    streaming: bool = False,
    resolved_config: dict | None = None,
    complexity_tier: str | None = None,
):
    """Get a LangChain ChatOpenAI instance with the provided config.

    If resolved_config is provided (from LLM gateway), use it.
    If complexity_tier is provided, look up from config.resolved_configs.
    Otherwise fall back to AgentConfig settings.

    #25: Injects trace_id as default header for full-chain propagation.
    """
    from app.core.trace_context import get_request_id, get_trace_id

    # Auto-resolve from pre-resolved configs if tier specified but no explicit resolved_config
    if not resolved_config and complexity_tier and config.resolved_configs:
        resolved_config = config.resolved_configs.get(complexity_tier)

    # 构建追踪头
    default_headers = {}
    trace_id = get_trace_id()
    request_id = get_request_id()
    if trace_id:
        default_headers["X-Trace-ID"] = trace_id
    if request_id:
        default_headers["X-Request-ID"] = request_id

    callbacks = _get_langfuse_callbacks(user_id=config.user_id)

    if resolved_config:
        _resolved_model = resolved_config.get("model") or model or config.model
        _resolved_base = resolved_config.get("base_url") or config.base_url
        logger.info(
            "[_get_llm] model=%s base_url=%s timeout=%s streaming=%s",
            _resolved_model,
            _resolved_base,
            resolved_config.get("timeout") or 300.0,
            streaming,
        )
        return ChatOpenAI(
            model=_resolved_model,
            api_key=resolved_config.get("api_key") or config.api_key,
            base_url=_resolved_base,
            temperature=resolved_config.get("temperature", config.temperature),
            streaming=streaming,
            timeout=resolved_config.get("timeout") or 300.0,
            default_headers=default_headers or None,
            callbacks=callbacks,
        )
    return ChatOpenAI(
        model=model or config.model,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=config.temperature,
        streaming=streaming,
        timeout=300.0,
        default_headers=default_headers or None,
        callbacks=callbacks,
    )


def _get_fallback_llm(
    config: AgentConfig, model: str | None = None, streaming: bool = False
):
    """Get a fallback LLM instance when primary provider is unavailable.

    Returns None if no fallback is configured.
    """
    from app.core.config import settings

    if not settings.AI_FALLBACK_API_KEY or not settings.AI_FALLBACK_BASE_URL:
        return None

    from app.core.trace_context import get_request_id, get_trace_id

    default_headers = {}
    trace_id = get_trace_id()
    request_id = get_request_id()
    if trace_id:
        default_headers["X-Trace-ID"] = trace_id
    if request_id:
        default_headers["X-Request-ID"] = request_id

    return ChatOpenAI(
        model=model or config.model,
        api_key=settings.AI_FALLBACK_API_KEY,
        base_url=settings.AI_FALLBACK_BASE_URL,
        temperature=config.temperature,
        streaming=streaming,
        timeout=300.0,  # Increased fallback timeout for complex queries
        default_headers=default_headers or None,
        callbacks=_get_langfuse_callbacks(user_id=config.user_id),
    )


# ─── Model Cascade Fallback (inspired by OpenClaw model-fallback.ts) ──────────

# Provider-level error keywords that warrant fallback (not content/format issues)
_PROVIDER_ERROR_KEYWORDS: set[str] = {
    "401",
    "402",
    "403",
    "429",
    "500",
    "502",
    "503",
    "insufficient",
    "quota",
    "balance",
    "payment",
    "rate limit",
    "rate_limit",
    "unauthorized",
    "authentication",
    "billing",
    "exceeded",
    "connection",
    "timeout",
    "connect",
}

# Auth errors should NOT retry same provider (skip to next)
_AUTH_ERROR_KEYWORDS: set[str] = {
    "401",
    "403",
    "unauthorized",
    "authentication",
    "invalid api key",
}

# Rate-limit errors can benefit from a short delay before next attempt
_RATE_LIMIT_KEYWORDS: set[str] = {
    "429",
    "rate limit",
    "rate_limit",
    "too many requests",
}

# Cooldown: track failed providers to avoid hammering them
# {provider_key: cooldown_until_timestamp}
_provider_cooldowns: dict[str, float] = {}
_COOLDOWN_SECONDS = 60  # Skip provider for 60s after failure


def _classify_error(error: Exception) -> str:
    """Classify an LLM error into: auth | rate_limit | provider | content."""
    error_str = str(error).lower()
    if any(kw in error_str for kw in _AUTH_ERROR_KEYWORDS):
        return "auth"
    if any(kw in error_str for kw in _RATE_LIMIT_KEYWORDS):
        return "rate_limit"
    if any(kw in error_str for kw in _PROVIDER_ERROR_KEYWORDS):
        return "provider"
    return "content"


def _provider_key(llm) -> str:
    """Extract a unique key for a provider instance."""
    base_url = getattr(llm, "openai_api_base", "") or ""
    model = getattr(llm, "model_name", "") or ""
    return f"{base_url}|{model}"


def _is_provider_cooled_down(key: str) -> bool:
    """Check if a provider is still in cooldown."""
    until = _provider_cooldowns.get(key, 0)
    return bool(until and time.time() < until)


def _set_provider_cooldown(key: str):
    """Put a provider into cooldown after failure."""
    _provider_cooldowns[key] = time.time() + _COOLDOWN_SECONDS


async def invoke_with_fallback(
    llm,
    messages: list,
    config: AgentConfig,
    model: str | None = None,
    streaming: bool = False,
    tool_schemas: list | None = None,
    complexity_tier: str | None = None,
    invoke_timeout: float = 45.0,
):
    """Invoke LLM with cascade fallback on provider-level failures.

    Cascade order:
      1. Primary LLM (provided)
      2. Fallback provider (from settings)
      3. Rate-limit retry: if error is 429, wait 2s and retry primary once
      4. Model-tier downgrade: if auth errors on both providers, try next lower tier

    Error-type-aware decisions:
      - auth errors: skip immediately to next provider (no retry)
      - rate_limit: short delay then retry once, then cascade
      - provider errors: cascade immediately
      - content errors: raise (not a provider issue)
      - timeout: cascade to next candidate (prevents hanging on unresponsive proxies)

    Cooldown: failed providers are skipped for 60s to avoid hammering.
    """
    candidates = [("primary", llm)]

    # Build fallback candidate
    fallback_llm = _get_fallback_llm(config, model=model, streaming=streaming)
    if fallback_llm:
        if tool_schemas:
            fallback_llm = fallback_llm.bind_tools(
                tool_schemas, parallel_tool_calls=True
            )
        candidates.append(("fallback", fallback_llm))

    last_error = None
    all_auth_errors = True  # Track if all failures are auth-related

    # ── Run before_llm_call hooks (PII sanitization, etc.) ──
    try:
        from app.agent.hooks import hook_registry

        messages = await hook_registry.run_before_llm(
            messages,
            {"user_id": config.user_id, "org_id": config.org_id, "model": model},
        )
    except Exception:
        logger.error(
            "[LLM Hooks] before_llm_call failed, continuing with original messages",
            exc_info=True,
        )

    for label, candidate_llm in candidates:
        pkey = _provider_key(candidate_llm)

        # Skip providers in cooldown
        if _is_provider_cooled_down(pkey):
            logger.info(f"[LLM Cascade] Skipping {label} (cooldown active)")
            continue

        try:
            result = await asyncio.wait_for(
                candidate_llm.ainvoke(messages),
                timeout=invoke_timeout,
            )
            return result
        except TimeoutError:
            logger.warning(
                "[LLM Cascade] %s timed out after %.0fs, cascading to next candidate",
                label,
                invoke_timeout,
            )
            last_error = TimeoutError(f"LLM invoke timeout after {invoke_timeout}s")
            all_auth_errors = False
            _set_provider_cooldown(pkey)
        except Exception as err:
            last_error = err
            error_type = _classify_error(err)

            if error_type == "content":
                # Content/format errors are not provider issues — raise immediately
                raise

            if error_type != "auth":
                all_auth_errors = False

            logger.warning(f"[LLM Cascade] {label} failed ({error_type}): {err}")
            _set_provider_cooldown(pkey)

            # Rate-limit: wait briefly and retry same provider once
            if error_type == "rate_limit" and label == "primary":
                logger.info("[LLM Cascade] Rate-limited, waiting 2s before retry...")
                await asyncio.sleep(2)
                try:
                    return await asyncio.wait_for(
                        candidate_llm.ainvoke(messages),
                        timeout=invoke_timeout,
                    )
                except TimeoutError:
                    logger.warning(
                        "[LLM Cascade] Rate-limit retry on %s timed out after %.0fs",
                        label,
                        invoke_timeout,
                    )
                    last_error = TimeoutError(
                        f"Rate-limit retry timeout after {invoke_timeout}s"
                    )
                    all_auth_errors = False
                    _set_provider_cooldown(pkey)
                except Exception as retry_err:
                    logger.warning(
                        f"[LLM Cascade] Retry after rate-limit also failed: {retry_err}"
                    )
                    last_error = retry_err
                    # Continue to next candidate

    # ── Model-tier downgrade: try a lower-tier model when auth errors exhaust all providers ──
    _TIER_DOWNGRADE = {"flagship": "power", "power": "balanced", "balanced": "economy"}
    if all_auth_errors and complexity_tier and config.resolved_configs:
        next_tier = _TIER_DOWNGRADE.get(complexity_tier)
        while next_tier:
            downgrade_cfg = config.resolved_configs.get(next_tier)
            if downgrade_cfg:
                logger.warning(
                    f"[LLM Cascade] All providers failed with auth errors for tier '{complexity_tier}', "
                    f"downgrading to tier '{next_tier}' model '{downgrade_cfg.get('model', '?')}'"
                )
                try:
                    downgrade_llm = _get_llm(
                        config, streaming=streaming, resolved_config=downgrade_cfg
                    )
                    if tool_schemas:
                        downgrade_llm = downgrade_llm.bind_tools(
                            tool_schemas, parallel_tool_calls=True
                        )
                    result = await asyncio.wait_for(
                        downgrade_llm.ainvoke(messages),
                        timeout=invoke_timeout,
                    )
                    logger.info(
                        f"[LLM Cascade] Model-tier downgrade to '{next_tier}' succeeded"
                    )
                    return result
                except TimeoutError:
                    logger.warning(
                        f"[LLM Cascade] Downgrade to '{next_tier}' timed out after {invoke_timeout}s"
                    )
                    last_error = TimeoutError(f"Downgrade to {next_tier} timed out")
                except Exception as dg_err:
                    logger.warning(
                        f"[LLM Cascade] Downgrade to '{next_tier}' also failed: {dg_err}"
                    )
                    last_error = dg_err
            next_tier = _TIER_DOWNGRADE.get(next_tier)

    # All candidates exhausted
    if last_error:
        raise last_error
    raise RuntimeError("[LLM Cascade] No LLM providers available")


def _messages_to_lc_format(messages) -> list[BaseMessage]:
    """Ensure messages are in LangChain format."""
    result = []
    for msg in messages:
        if isinstance(msg, BaseMessage):
            result.append(msg)
        elif isinstance(msg, dict):
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                result.append(SystemMessage(content=content))
            elif role == "user":
                result.append(HumanMessage(content=content))
            elif role == "assistant":
                result.append(
                    AIMessage(
                        content=content,
                        additional_kwargs=msg.get("additional_kwargs", {}),
                    )
                )
            elif role == "tool":
                result.append(
                    ToolMessage(
                        content=content,
                        tool_call_id=msg.get("tool_call_id", ""),
                        name=msg.get("name", ""),
                    )
                )
    return result


def _format_validation_error(
    tool_name: str, error: Exception, schema: dict | None = None
) -> str:
    """
    Format a schema validation error with field-level guidance for the LLM.

    Instead of raw jsonschema error text, produces a structured message
    that helps the LLM understand exactly which field to fix.
    """
    try:
        import jsonschema

        if isinstance(error, jsonschema.ValidationError):
            field_path = (
                " → ".join(str(p) for p in error.absolute_path)
                if error.absolute_path
                else "(root)"
            )
            lines = [f"参数校验失败 [{tool_name}]:"]
            lines.append(f"  错误字段: {field_path}")
            lines.append(f"  问题: {error.message}")

            # Add expected type/enum info
            if error.schema:
                if "type" in error.schema:
                    lines.append(f"  期望类型: {error.schema['type']}")
                if "enum" in error.schema:
                    lines.append(f"  允许值: {error.schema['enum']}")
                if "description" in error.schema:
                    lines.append(f"  字段说明: {error.schema['description']}")

            # Show required fields if it's a missing-property error
            if error.validator == "required" and schema:
                required = schema.get("required", [])
                props = schema.get("properties", {})
                if required:
                    field_hints = []
                    for r in required:
                        desc = props.get(r, {}).get("description", "")
                        ftype = props.get(r, {}).get("type", "")
                        field_hints.append(
                            f"    - {r} ({ftype}): {desc}"
                            if desc
                            else f"    - {r} ({ftype})"
                        )
                    lines.append("  必填字段:")
                    lines.extend(field_hints)

            return "\n".join(lines)
    except Exception:
        pass

    # Fallback for non-jsonschema errors
    return f"参数校验失败 [{tool_name}]: {error}"


def _try_extract_tool_names(concatenated_name: str) -> list[str]:
    """
    Gemini concatenation bug workaround: Extract ALL valid tool names
    from a concatenated string like 'get_daily_briefingget_pending_approvals'.

    Returns a list of matched tool names (may be empty).
    """
    all_schemas = _tool_schemas_cache or get_all_tools_schema()
    # Sort by length descending to match longest tool name first
    known_names = sorted(
        [s["function"]["name"] for s in all_schemas],
        key=len,
        reverse=True,
    )

    found: list[str] = []
    remaining = concatenated_name
    while remaining:
        matched = False
        for name in known_names:
            if remaining.startswith(name):
                found.append(name)
                remaining = remaining[len(name) :]
                matched = True
                break
        if not matched:
            break  # Unrecognizable remainder, stop parsing

    return found if len(found) > 1 else []  # Only useful when multiple names found
