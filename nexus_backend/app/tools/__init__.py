import importlib
import inspect
import logging
import pkgutil

from .base_tool import BaseTool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy registry: tool_name -> (module_path, class_name)
#
# Keys MUST match the `name` class-attribute on each tool.
# Module paths are absolute (relative to the package root used by the app).
# ---------------------------------------------------------------------------
_TOOL_MODULES: dict[str, tuple[str, str]] = {
    # tender_tool
    "analyze_tender_document": ("app.tools.tender_tool", "TenderAnalysisTool"),
    # battlecard_tool
    "get_battlecard": ("app.tools.battlecard_tool", "BattlecardTool"),
    "list_competitors": ("app.tools.battlecard_tool", "ListCompetitorsTool"),
    # approval_tools
    "approve_request": ("app.tools.approval_tools", "ApprovalTool"),
    "reject_request": ("app.tools.approval_tools", "RejectTool"),
    "get_pending_approvals": ("app.tools.approval_tools", "PendingApprovalsTool"),
    "submit_approval_on_behalf": ("app.tools.approval_tools", "SubmitApprovalOnBehalfTool"),
    "get_employee_info": ("app.tools.approval_tools", "GetEmployeeInfoTool"),
    "get_employee_approval_history": ("app.tools.approval_tools", "GetEmployeeApprovalHistoryTool"),
    # operational_tools
    "get_performance_report": ("app.tools.operational_tools", "PerformanceReportTool"),
    "get_company_stats": ("app.tools.operational_tools", "CompanyStatsTool"),
    "query_knowledge_base": ("app.tools.operational_tools", "KnowledgeBaseTool"),
    "award_badge": ("app.tools.operational_tools", "AwardBadgeTool"),
    # project_tools
    "get_projects": ("app.tools.project_tools", "ProjectListTool"),
    "create_project_event": ("app.tools.project_tools", "CreateEventTool"),
    "create_project": ("app.tools.project_tools", "CreateProjectTool"),
    "generate_weekly_report": ("app.tools.project_tools", "WeeklyReportTool"),
    # oa_tools
    "create_leave_request": ("app.tools.oa_tools", "LeaveRequestTool"),
    "query_leave_status": ("app.tools.oa_tools", "LeaveQueryTool"),
    "book_meeting": ("app.tools.oa_tools", "MeetingBookingTool"),
    "assign_task": ("app.tools.oa_tools", "TaskAssignmentTool"),
    "create_work_handover": ("app.tools.oa_tools", "WorkHandoverTool"),
    "generate_onboarding_checklist": ("app.tools.oa_tools", "OnboardingChecklistTool"),
    "send_notification": ("app.tools.oa_tools", "SendNotificationTool"),
    # finance_tools
    "create_expense_claim": ("app.tools.finance_tools", "ExpenseClaimTool"),
    "query_expense_status": ("app.tools.finance_tools", "ExpenseQueryTool"),
    "query_budget": ("app.tools.finance_tools", "BudgetQueryTool"),
    "query_salary": ("app.tools.finance_tools", "SalaryQueryTool"),
    "recognize_invoice": ("app.tools.finance_tools", "InvoiceOCRTool"),
    # hr_tools
    "query_attendance": ("app.tools.hr_tools", "AttendanceQueryTool"),
    "query_team_attendance": ("app.tools.hr_tools", "TeamAttendanceTool"),
    "get_employee_profile": ("app.tools.hr_tools", "EmployeeProfileTool"),
    "create_performance_review": ("app.tools.hr_tools", "PerformanceReviewTool"),
    "manage_recruitment": ("app.tools.hr_tools", "RecruitmentTool"),
    # boss_tools (领导专属)
    "smart_approve": ("app.tools.boss_tools", "SmartApprovalTool"),
    "get_daily_briefing": ("app.tools.boss_tools", "DailyBriefingTool"),
    "get_business_dashboard": ("app.tools.boss_tools", "BusinessDashboardTool"),
    "get_team_insight": ("app.tools.boss_tools", "TeamInsightTool"),
    "publish_announcement": ("app.tools.boss_tools", "AnnouncementTool"),
    "generate_customer_profile": ("app.tools.boss_tools", "CustomerProfileTool"),
    # contract_tools
    "analyze_contract": ("app.tools.contract_tools", "ContractAnalysisTool"),
    # crm_tools
    "get_customers": ("app.tools.crm_tools", "GetCustomersTool"),
    "get_customer_detail": ("app.tools.crm_tools", "GetCustomerDetailTool"),
    "create_customer": ("app.tools.crm_tools", "CreateCustomerTool"),
    "update_customer": ("app.tools.crm_tools", "UpdateCustomerTool"),
    "add_follow_up": ("app.tools.crm_tools", "AddFollowUpTool"),
    "get_follow_ups": ("app.tools.crm_tools", "GetFollowUpsTool"),
    "update_customer_stage": ("app.tools.crm_tools", "UpdateCustomerStageTool"),
    "get_sales_pipeline": ("app.tools.crm_tools", "GetSalesPipelineTool"),
    # contract_crud_tools
    "get_contracts": ("app.tools.contract_crud_tools", "GetContractsTool"),
    "create_contract": ("app.tools.contract_crud_tools", "CreateContractTool"),
    "get_expiring_contracts": ("app.tools.contract_crud_tools", "GetExpiringContractsTool"),
    # strategy_tools (Phase 4)
    "analyze_data_attribution": ("app.tools.strategy_tools", "DataAttributionTool"),
    "strategy_simulation": ("app.tools.strategy_tools", "StrategySimulationTool"),
    # scheduled_task_tools (user-defined scheduled tasks)
    "create_scheduled_task": ("app.tools.scheduled_task_tools", "CreateScheduledTaskTool"),
    "list_scheduled_tasks": ("app.tools.scheduled_task_tools", "ListScheduledTasksTool"),
    "delete_scheduled_task": ("app.tools.scheduled_task_tools", "DeleteScheduledTaskTool"),
    # ask_user (P1-7: agent proactive questioning)
    "ask_user": ("app.tools.ask_user_tool", "AskUserTool"),
    # web_search (P0: 联网搜索能力)
    "web_search": ("app.tools.web_search_tool", "WebSearchTool"),
    # llm_task (P1: 轻量子任务委派)
    "llm_task": ("app.tools.llm_task_tool", "LLMTaskTool"),
    # bidding_tool (招投标查询)
    "search_bidding_projects": ("app.tools.bidding_tool", "BiddingSearchTool"),
    # system_config_tools (系统配置)
    "list_system_configs": ("app.tools.system_config_tools", "ListSystemConfigsTool"),
    "update_system_config": ("app.tools.system_config_tools", "UpdateSystemConfigTool"),
    # organization_tools (组织架构)
    "list_departments": ("app.tools.organization_tools", "ListDepartmentsTool"),
    "create_department": ("app.tools.organization_tools", "CreateDepartmentTool"),
    "update_department": ("app.tools.organization_tools", "UpdateDepartmentTool"),
    "list_employees": ("app.tools.organization_tools", "ListEmployeesTool"),
    "get_employee_detail": ("app.tools.organization_tools", "GetEmployeeDetailTool"),
    "create_employee": ("app.tools.organization_tools", "CreateEmployeeTool"),
    "update_employee": ("app.tools.organization_tools", "UpdateEmployeeTool"),
    "org_statistics": ("app.tools.organization_tools", "OrgStatisticsTool"),
    # asset_tools (资产管理)
    "list_assets": ("app.tools.asset_tools", "ListAssetsTool"),
    "get_asset_detail": ("app.tools.asset_tools", "GetAssetDetailTool"),
    "create_asset": ("app.tools.asset_tools", "CreateAssetTool"),
    "update_asset": ("app.tools.asset_tools", "UpdateAssetTool"),
    "transfer_asset": ("app.tools.asset_tools", "TransferAssetTool"),
    "asset_statistics": ("app.tools.asset_tools", "AssetStatisticsTool"),
    # work_order_tools (工单系统)
    "create_work_order": ("app.tools.work_order_tools", "CreateWorkOrderTool"),
    "list_work_orders": ("app.tools.work_order_tools", "ListWorkOrdersTool"),
    "get_work_order_detail": ("app.tools.work_order_tools", "GetWorkOrderDetailTool"),
    "update_work_order": ("app.tools.work_order_tools", "UpdateWorkOrderTool"),
    "work_order_statistics": ("app.tools.work_order_tools", "WorkOrderStatisticsTool"),
    # attendance_tools (考勤管理)
    "clock_in_out": ("app.tools.attendance_tools", "ClockInOutTool"),
    "get_attendance_record": ("app.tools.attendance_tools", "GetAttendanceRecordTool"),
    "create_shift_schedule": ("app.tools.attendance_tools", "CreateShiftScheduleTool"),
    "list_shift_schedules": ("app.tools.attendance_tools", "ListShiftSchedulesTool"),
    "attendance_statistics": ("app.tools.attendance_tools", "AttendanceStatisticsTool"),
    "request_leave": ("app.tools.attendance_tools", "RequestLeaveTool"),
    # expense_tools (报销管理)
    "submit_expense": ("app.tools.expense_tools", "SubmitExpenseTool"),
    "list_expenses": ("app.tools.expense_tools", "ListExpensesTool"),
    "approve_expense": ("app.tools.expense_tools", "ApproveExpenseTool"),
    "check_budget": ("app.tools.expense_tools", "CheckBudgetTool"),
    # inventory_tools (库存管理)
    "list_inventory": ("app.tools.inventory_tools", "ListInventoryTool"),
    "inventory_in": ("app.tools.inventory_tools", "InventoryInTool"),
    "inventory_out": ("app.tools.inventory_tools", "InventoryOutTool"),
    "inventory_statistics": ("app.tools.inventory_tools", "InventoryStatisticsTool"),
    # certificate_tools (证照管理)
    "list_certificates": ("app.tools.certificate_tools", "ListCertificatesTool"),
    "create_certificate": ("app.tools.certificate_tools", "CreateCertificateTool"),
    "expiring_certificates": ("app.tools.certificate_tools", "ExpiringCertsTool"),
    "renew_certificate": ("app.tools.certificate_tools", "RenewCertificateTool"),
    # approval_flow_tools (审批流程)
    "list_approval_flows": ("app.tools.approval_flow_tools", "ListApprovalFlowsTool"),
    "create_approval_flow": ("app.tools.approval_flow_tools", "CreateApprovalFlowTool"),
    # ai_insight_tools (AI智能分析 - Phase 3)
    "smart_report": ("app.tools.ai_insight_tools", "SmartReportTool"),
    "anomaly_detection": ("app.tools.ai_insight_tools", "AnomalyDetectionTool"),
    "predictive_maintenance": ("app.tools.ai_insight_tools", "PredictiveMaintenanceTool"),
    "auto_dispatch": ("app.tools.ai_insight_tools", "AutoDispatchTool"),
    "meeting_summary": ("app.tools.ai_insight_tools", "MeetingSummaryTool"),
    "onboarding_assistant": ("app.tools.ai_insight_tools", "OnboardingAssistantTool"),
    # workflow_tools (复合工作流)
    "process_onboarding": ("app.tools.workflow_tools", "ProcessOnboardingTool"),
    "process_resignation": ("app.tools.workflow_tools", "ProcessResignationTool"),
    "process_asset_lifecycle": ("app.tools.workflow_tools", "ProcessAssetLifecycleTool"),
}

# VMD tools are optional — kept separate so ImportError is tolerated
_VMD_TOOL_MODULES: dict[str, tuple[str, str]] = {
    # vmd_content_tools
    "generate_product_manual": ("app.tools.vmd_content_tools", "GenerateProductManualTool"),
    "generate_whitepaper": ("app.tools.vmd_content_tools", "GenerateWhitepaperTool"),
    "generate_application_note": ("app.tools.vmd_content_tools", "GenerateApplicationNoteTool"),
    "generate_social_post": ("app.tools.vmd_content_tools", "GenerateSocialPostTool"),
    # vmd_tender_tools
    "generate_bid_document": ("app.tools.vmd_tender_tools", "GenerateBidDocumentTool"),
    "generate_deviation_table": ("app.tools.vmd_tender_tools", "GenerateDeviationTableTool"),
    "check_bid_compliance": ("app.tools.vmd_tender_tools", "CheckBidComplianceTool"),
    "extract_bid_requirements": ("app.tools.vmd_tender_tools", "ExtractBidRequirementsTool"),
    # vmd_sales_tools
    "generate_sales_script": ("app.tools.vmd_sales_tools", "GenerateSalesScriptTool"),
    "generate_competitor_comparison": ("app.tools.vmd_sales_tools", "GenerateCompetitorComparisonTool"),
    "generate_training_material": ("app.tools.vmd_sales_tools", "GenerateTrainingMaterialTool"),
    "generate_quotation_template": ("app.tools.vmd_sales_tools", "GenerateQuotationTemplateTool"),
    # vmd_synergy_tools
    "monitor_industry_trends": ("app.tools.vmd_synergy_tools", "MonitorIndustryTrendsTool"),
    "generate_market_research": ("app.tools.vmd_synergy_tools", "GenerateMarketResearchTool"),
    "generate_competitor_analysis": ("app.tools.vmd_synergy_tools", "GenerateCompetitorAnalysisTool"),
    "aggregate_customer_feedback": ("app.tools.vmd_synergy_tools", "AggregateCustomerFeedbackTool"),
    # vmd_operation_tools
    "generate_maintenance_reminder": ("app.tools.vmd_operation_tools", "GenerateMaintenanceReminderTool"),
    "generate_faq_response": ("app.tools.vmd_operation_tools", "GenerateFaqResponseTool"),
    "generate_repurchase_campaign": ("app.tools.vmd_operation_tools", "GenerateRepurchaseCampaignTool"),
    "customer_lifecycle_analysis": ("app.tools.vmd_operation_tools", "CustomerLifecycleAnalysisTool"),
}

# ---------------------------------------------------------------------------
# Runtime registry — populated lazily as tools are first requested
# ---------------------------------------------------------------------------
TOOL_REGISTRY: dict[str, BaseTool] = {}
_all_loaded = False


def register_tool(tool: BaseTool):
    """Register an externally-created tool instance (backward-compat)."""
    TOOL_REGISTRY[tool.name] = tool


def _load_tool(name: str) -> BaseTool | None:
    """Import a single tool by name and cache it in TOOL_REGISTRY."""
    if name in TOOL_REGISTRY:
        return TOOL_REGISTRY[name]

    spec = _TOOL_MODULES.get(name) or _VMD_TOOL_MODULES.get(name)
    if not spec:
        return None

    module_path, class_name = spec
    is_vmd = name in _VMD_TOOL_MODULES
    try:
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        instance = cls()
        TOOL_REGISTRY[instance.name] = instance
        return instance
    except ImportError:
        if is_vmd:
            # VMD modules are optional; silently skip
            return None
        logger.error("Failed to import tool %s from %s", name, module_path)
        return None
    except Exception:
        logger.exception("Error loading tool %s from %s", name, module_path)
        return None


def _load_all():
    """Force-load every registered tool module (called once at agent init)."""
    global _all_loaded
    if _all_loaded:
        return

    for name in _TOOL_MODULES:
        _load_tool(name)
    for name in _VMD_TOOL_MODULES:
        _load_tool(name)

    _auto_discover()
    _all_loaded = True


def _auto_discover():
    """Scan app/tools/*.py for BaseTool subclasses not in _TOOL_MODULES.

    This allows new tools to be added by simply placing a .py file in
    app/tools/ without touching __init__.py or _TOOL_MODULES.
    """
    import app.tools as tools_pkg

    known = set(_TOOL_MODULES) | set(_VMD_TOOL_MODULES)
    for _importer, modname, ispkg in pkgutil.iter_modules(
        tools_pkg.__path__, "app.tools."
    ):
        if ispkg or modname.endswith(("__init__", "base_tool")):
            continue
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue  # optional modules may fail — skip silently
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseTool)
                and obj is not BaseTool
                and not inspect.isabstract(obj)
            ):
                try:
                    instance = obj()
                    if instance.name not in TOOL_REGISTRY and instance.name not in known:
                        TOOL_REGISTRY[instance.name] = instance
                        logger.debug("Auto-discovered tool: %s from %s", instance.name, modname)
                except Exception:
                    pass  # skip tools that fail to instantiate


def get_tool(name: str) -> BaseTool | None:
    """Return a tool by name, lazily importing it if needed."""
    return TOOL_REGISTRY.get(name) or _load_tool(name)


def _sanitize_schema(properties: dict) -> dict:
    """清洗工具参数 schema，确保兼容 OpenAI / Gemini 等不同 LLM 后端。

    - enum 值如果是 dict，转为 list(keys)
    - 移除 Gemini 不支持的 examples 字段
    """
    if not isinstance(properties, dict):
        return properties
    cleaned = {}
    for key, prop in properties.items():
        if not isinstance(prop, dict):
            cleaned[key] = prop
            continue
        prop = dict(prop)  # shallow copy
        # dict enum → list of keys
        if "enum" in prop and isinstance(prop["enum"], dict):
            prop["enum"] = list(prop["enum"])
        # remove unsupported 'examples' field
        prop.pop("examples", None)
        cleaned[key] = prop
    return cleaned


def get_all_tools_schema():
    """Generates the OpenAI tools schema list dynamically.

    Forces all tools to be loaded first (called once at agent init time).
    """
    _load_all()
    schemas = []
    for tool in TOOL_REGISTRY.values():
        params = tool.parameters
        # 防御性清洗 properties
        if isinstance(params, dict) and "properties" in params:
            params = {**params, "properties": _sanitize_schema(params["properties"])}
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": params,
                },
            }
        )
    return schemas
