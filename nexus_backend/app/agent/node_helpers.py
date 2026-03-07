"""
Shared imports, helpers, constants and Pydantic models for graph nodes.

All node modules import from here to avoid circular dependencies.
"""

import logging

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
    record_hallucination,  # noqa: F401
    record_llm_latency,  # noqa: F401
    record_tool_execution,  # noqa: F401
)
from app.services.content_moderation import sanitize_output, scan_content  # noqa: F401
from app.services.error_recovery_service import llm_circuit_breaker, tool_circuit_breaker  # noqa: F401
from app.services.plugin_system_service import ExtensionPoint, plugin_system_service  # noqa: F401
from app.tools import get_all_tools_schema, get_tool

logger = logging.getLogger(__name__)

# Long-running tools that need extended timeout (120s instead of default 30s)
LONG_RUNNING_TOOLS: set[str] = {
    "generate_product_manual",
    "generate_faq_response",
    "generate_training_material",
    "generate_weekly_report",
    "generate_competitor_analysis",
    "generate_tender_analysis",
    "generate_contract_summary",
    "batch_analyze_documents",
    "query_knowledge_base",
    "strategy_simulation",
    "get_company_stats",
}


# ─── Pydantic models for structured LLM output in reflect_node ───────────────


class GroundednessCheck(BaseModel):
    """RAG groundedness evaluation result."""

    is_grounded: bool = Field(description="Whether the response is grounded in reference knowledge")
    reason: str = Field(default="", description="Reason for the evaluation")
    score: float = Field(default=0.5, ge=0.0, le=1.0, description="Groundedness score 0-1")


class HallucinationCheck(BaseModel):
    """LLM-based hallucination detection result."""

    is_hallucination: bool = Field(description="Whether the response contains fabricated information")
    reason: str = Field(default="", description="Reason for the evaluation")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence score 0-1")


class CriticResult(BaseModel):
    """P1-5: Independent critic evaluation of agent response quality."""

    completeness: float = Field(default=0.5, ge=0.0, le=1.0, description="回答是否完整覆盖用户问题")
    relevance: float = Field(default=0.5, ge=0.0, le=1.0, description="回答与用户意图的相关性")
    accuracy: float = Field(default=0.5, ge=0.0, le=1.0, description="信息准确性（基于工具结果）")
    passed: bool = Field(default=True, description="是否通过评审")
    improvement_suggestion: str = Field(default="", description="改进建议（未通过时提供）")


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

# Always included regardless of intent
_ALWAYS_INCLUDE_TOOLS: set[str] = {
    "ask_user", "web_search", "llm_task",
}

# Domain → tool name sets
_DOMAIN_TOOL_MAP: dict[str, set[str]] = {
    "oa_leave": {
        "create_leave_request", "query_leave_status", "request_leave",
        "book_meeting", "assign_task", "create_work_handover",
        "generate_onboarding_checklist",
    },
    "attendance": {
        "clock_in_out", "get_attendance_record", "attendance_statistics",
        "create_shift_schedule", "list_shift_schedules", "request_leave",
        "query_attendance", "query_team_attendance",
    },
    "approval": {
        "approve_request", "reject_request", "get_pending_approvals",
        "submit_approval_on_behalf", "get_employee_approval_history",
        "smart_approve", "list_approval_flows", "create_approval_flow",
        "approve_expense",
    },
    "finance": {
        "create_expense_claim", "query_expense_status", "query_budget",
        "query_salary", "recognize_invoice", "submit_expense",
        "list_expenses", "approve_expense", "check_budget",
    },
    "project": {
        "get_projects", "create_project", "create_project_event",
        "generate_weekly_report", "assign_task",
        "list_work_orders", "create_work_order", "get_work_order_detail",
        "update_work_order", "work_order_statistics",
    },
    "crm": {
        "get_customers", "get_customer_detail", "create_customer",
        "update_customer", "add_follow_up", "get_follow_ups",
        "update_customer_stage", "get_sales_pipeline",
        "get_contracts", "create_contract", "get_expiring_contracts",
        "analyze_contract", "generate_customer_profile",
    },
    "hr": {
        "get_employee_profile", "get_employee_detail", "get_employee_info",
        "list_employees", "create_employee", "update_employee",
        "create_performance_review", "manage_recruitment",
        "list_departments", "create_department", "update_department",
        "org_statistics",
    },
    "asset": {
        "list_assets", "get_asset_detail", "create_asset",
        "update_asset", "transfer_asset", "asset_statistics",
    },
    "tender": {
        "analyze_tender_document", "get_battlecard", "list_competitors",
        "search_bidding_projects",
        "generate_bid_document", "generate_deviation_table",
        "check_bid_compliance", "extract_bid_requirements",
    },
    "analytics": {
        "get_performance_report", "get_company_stats",
        "smart_report", "anomaly_detection",
        "get_business_dashboard", "get_team_insight",
        "analyze_data_attribution", "strategy_simulation",
    },
    "schedule": {
        "create_scheduled_task", "list_scheduled_tasks",
        "delete_scheduled_task", "get_daily_briefing",
        "get_pending_approvals", "assign_task",
    },
    "vmd_content": {
        "generate_product_manual", "generate_whitepaper",
        "generate_application_note", "generate_social_post",
        "generate_sales_script", "generate_competitor_comparison",
        "generate_training_material", "generate_quotation_template",
    },
    "vmd_market": {
        "monitor_industry_trends", "generate_market_research",
        "generate_competitor_analysis", "aggregate_customer_feedback",
        "generate_maintenance_reminder", "generate_faq_response",
        "generate_repurchase_campaign", "customer_lifecycle_analysis",
    },
    "admin": {
        "list_system_configs", "update_system_config",
        "list_certificates", "create_certificate",
        "expiring_certificates", "renew_certificate",
        "process_onboarding", "process_resignation",
        "process_asset_lifecycle",
    },
}

# Keyword → domain(s) mapping — reuses router.py keyword vocabulary
_KEYWORD_DOMAIN_MAP: dict[str, list[str]] = {
    # OA / Leave
    "请假": ["oa_leave"], "出差": ["oa_leave"], "会议": ["oa_leave"],
    "日程": ["oa_leave", "schedule"], "交接": ["oa_leave"],
    # Attendance
    "考勤": ["attendance"], "打卡": ["attendance"], "补卡": ["attendance"],
    "加班": ["attendance"], "排班": ["attendance"],
    # Approval
    "审批": ["approval"], "批准": ["approval"], "拒绝": ["approval"],
    "驳回": ["approval"], "批了": ["approval"], "不批": ["approval"],
    "同意": ["approval"], "通过": ["approval"],
    # Finance
    "报销": ["finance"], "预算": ["finance"], "工资": ["finance"],
    "薪资": ["finance"], "发票": ["finance"], "开票": ["finance"],
    "付款": ["finance"], "转账": ["finance"], "发工资": ["finance"],
    # Project
    "项目": ["project"], "进度": ["project"], "任务": ["project", "schedule"],
    "工单": ["project"],
    # CRM / Sales
    "客户": ["crm"], "合同": ["crm"], "商机": ["crm"],
    "线索": ["crm"], "跟进": ["crm"], "漏斗": ["crm"],
    # HR
    "员工": ["hr"], "通讯录": ["hr"], "培训": ["hr"],
    "招聘": ["hr"], "绩效": ["hr", "analytics"], "部门": ["hr"],
    "入职": ["hr", "admin"], "离职": ["hr", "admin"],
    # Asset
    "设备": ["asset"], "资产": ["asset"], "车辆": ["asset"],
    "快递": ["asset"], "印章": ["asset"],
    # Tender / Bidding
    "招标": ["tender"], "投标": ["tender"], "标书": ["tender"],
    "竞品": ["tender", "vmd_content"], "battlecard": ["tender"],
    # Analytics
    "分析": ["analytics"], "报告": ["analytics"], "统计": ["analytics"],
    "趋势": ["analytics", "vmd_market"], "预测": ["analytics"],
    "仪表盘": ["analytics"], "dashboard": ["analytics"],
    "总结": ["analytics"], "经营": ["analytics"],
    # Schedule
    "待办": ["schedule", "approval"], "日报": ["schedule"],
    "周报": ["project"], "简报": ["schedule", "analytics"],
    "定时": ["schedule"],
    # VMD
    "白皮书": ["vmd_content"], "文案": ["vmd_content"],
    "话术": ["vmd_content"], "手册": ["vmd_content"],
    "市场": ["vmd_market"], "舆情": ["vmd_market"],
    # Admin
    "证照": ["admin"], "盖章": ["admin"], "用印": ["admin"],
    "签署": ["admin"], "公告": ["admin", "approval"],
    "通知": ["admin", "approval", "oa_leave", "project"],
    # Knowledge
    "知识库": ["analytics"], "搜索": [],
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


def _get_tool_schemas(user_role: str | None = None, intent_summary: str | None = None):
    """Get tool schemas with caching.

    Filters by: 1) user role (RBAC), 2) intent domain (token reduction).
    """
    global _tool_schemas_cache, _tool_schemas_count
    schemas = get_all_tools_schema()
    if _tool_schemas_cache is None or len(schemas) != _tool_schemas_count:
        _tool_schemas_cache = schemas
        _tool_schemas_count = len(schemas)

    if not user_role:
        filtered = list(_tool_schemas_cache)
    else:
        # Filter schemas by user role — exclude tools the user cannot execute
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

    # Intent-based filtering — only when intent detected a specific domain
    if intent_summary:
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

    return filtered


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _get_llm(
    config: AgentConfig, model: str | None = None, streaming: bool = False, resolved_config: dict | None = None
):
    """Get a LangChain ChatOpenAI instance with the provided config.

    If resolved_config is provided (from LLM gateway), use it.
    Otherwise fall back to AgentConfig settings.

    #25: Injects trace_id as default header for full-chain propagation.
    """
    from app.core.trace_context import get_request_id, get_trace_id

    # 构建追踪头
    default_headers = {}
    trace_id = get_trace_id()
    request_id = get_request_id()
    if trace_id:
        default_headers["X-Trace-ID"] = trace_id
    if request_id:
        default_headers["X-Request-ID"] = request_id

    # Langfuse CallbackHandler injection
    callbacks = None
    try:
        from app.core.config import settings

        if settings.LANGFUSE_ENABLED:
            from langfuse.callback import CallbackHandler as LangfuseCallbackHandler

            callbacks = [
                LangfuseCallbackHandler(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_HOST,
                )
            ]
    except Exception:
        pass  # Langfuse not available, skip

    if resolved_config:
        return ChatOpenAI(
            model=resolved_config.get("model", model or config.model),
            api_key=resolved_config.get("api_key", config.api_key),
            base_url=resolved_config.get("base_url", config.base_url),
            temperature=resolved_config.get("temperature", config.temperature),
            streaming=streaming,
            timeout=resolved_config.get("timeout", 90.0),
            default_headers=default_headers or None,
            callbacks=callbacks,
        )
    return ChatOpenAI(
        model=model or config.model,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=config.temperature,
        streaming=streaming,
        timeout=90.0,
        default_headers=default_headers or None,
        callbacks=callbacks,
    )


def _get_fallback_llm(config: AgentConfig, model: str | None = None, streaming: bool = False):
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
        timeout=90.0,
        default_headers=default_headers or None,
    )


async def invoke_with_fallback(
    llm,
    messages: list,
    config: AgentConfig,
    model: str | None = None,
    streaming: bool = False,
    tool_schemas: list | None = None,
):
    """Invoke LLM with automatic fallback to backup provider on failure.

    Tries primary LLM first. If it fails (payment, rate limit, auth, server error),
    automatically retries with fallback provider.
    """
    try:
        return await llm.ainvoke(messages)
    except Exception as primary_error:
        error_str = str(primary_error).lower()
        # Only fallback on provider-level errors, not on content/format issues
        is_provider_error = any(
            kw in error_str
            for kw in [
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
            ]
        )
        if not is_provider_error:
            raise

        fallback_llm = _get_fallback_llm(config, model=model, streaming=streaming)
        if not fallback_llm:
            raise

        logger.warning(f"[LLM Fallback] Primary failed: {primary_error}. Switching to fallback provider.")
        if tool_schemas:
            fallback_llm = fallback_llm.bind_tools(tool_schemas, parallel_tool_calls=True)
        return await fallback_llm.ainvoke(messages)


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
                result.append(AIMessage(content=content, additional_kwargs=msg.get("additional_kwargs", {})))
            elif role == "tool":
                result.append(
                    ToolMessage(content=content, tool_call_id=msg.get("tool_call_id", ""), name=msg.get("name", ""))
                )
    return result


def _format_validation_error(tool_name: str, error: Exception, schema: dict | None = None) -> str:
    """
    Format a schema validation error with field-level guidance for the LLM.

    Instead of raw jsonschema error text, produces a structured message
    that helps the LLM understand exactly which field to fix.
    """
    try:
        import jsonschema

        if isinstance(error, jsonschema.ValidationError):
            field_path = " → ".join(str(p) for p in error.absolute_path) if error.absolute_path else "(root)"
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
                        field_hints.append(f"    - {r} ({ftype}): {desc}" if desc else f"    - {r} ({ftype})")
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
    all_schemas = get_all_tools_schema()
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
