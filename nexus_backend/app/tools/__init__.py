from .approval_tools import (
    ApprovalTool,
    GetEmployeeApprovalHistoryTool,
    GetEmployeeInfoTool,
    PendingApprovalsTool,
    RejectTool,
    SubmitApprovalOnBehalfTool,
)
from .base_tool import BaseTool
from .battlecard_tool import BattlecardTool

# 领导专属工具
from .boss_tools import (
    AnnouncementTool,
    BusinessDashboardTool,
    CustomerProfileTool,
    DailyBriefingTool,
    SmartApprovalTool,
    TeamInsightTool,
)

# 合同 CRUD 工具
from .contract_crud_tools import (
    CreateContractTool,
    GetContractsTool,
    GetExpiringContractsTool,
)

# 合同分析工具
from .contract_tools import ContractAnalysisTool

# CRM 客户管理工具
from .crm_tools import (
    AddFollowUpTool,
    CreateCustomerTool,
    GetCustomerDetailTool,
    GetCustomersTool,
    GetFollowUpsTool,
    GetSalesPipelineTool,
    UpdateCustomerStageTool,
    UpdateCustomerTool,
)

# 财务管理工具
from .finance_tools import (
    BudgetQueryTool,
    ExpenseClaimTool,
    ExpenseQueryTool,
    InvoiceOCRTool,
    SalaryQueryTool,
)

# HR 人力资源工具
from .hr_tools import (
    AttendanceQueryTool,
    EmployeeProfileTool,
    PerformanceReviewTool,
    RecruitmentTool,
    TeamAttendanceTool,
)

# OA 办公自动化工具
from .oa_tools import (
    LeaveQueryTool,
    LeaveRequestTool,
    MeetingBookingTool,
    OnboardingChecklistTool,
    TaskAssignmentTool,
    WorkHandoverTool,
)
from .operational_tools import (
    AwardBadgeTool,
    CompanyStatsTool,
    KnowledgeBaseTool,
    PerformanceReportTool,
)
from .project_tools import CreateEventTool, CreateProjectTool, ProjectListTool, WeeklyReportTool

# 战略分析工具 (Phase 4)
from .strategy_tools import DataAttributionTool, StrategySimulationTool
from .tender_tool import TenderAnalysisTool

# Registry of all available tools
# P1: Strategy Pattern Registry
TOOL_REGISTRY: dict[str, BaseTool] = {}


def register_tool(tool: BaseTool):
    TOOL_REGISTRY[tool.name] = tool


register_tool(TenderAnalysisTool())
register_tool(BattlecardTool())
register_tool(ApprovalTool())
register_tool(RejectTool())
register_tool(PendingApprovalsTool())

# AI 助手代理工具（二级权限）
register_tool(SubmitApprovalOnBehalfTool())
register_tool(GetEmployeeInfoTool())
register_tool(GetEmployeeApprovalHistoryTool())
register_tool(PerformanceReportTool())
register_tool(CompanyStatsTool())
register_tool(KnowledgeBaseTool())
register_tool(AwardBadgeTool())
register_tool(ProjectListTool())
register_tool(CreateEventTool())
register_tool(CreateProjectTool())
register_tool(WeeklyReportTool())

# 注册 OA 工具
register_tool(LeaveRequestTool())
register_tool(LeaveQueryTool())
register_tool(MeetingBookingTool())
register_tool(TaskAssignmentTool())
register_tool(WorkHandoverTool())
register_tool(OnboardingChecklistTool())

# 注册财务工具
register_tool(ExpenseClaimTool())
register_tool(ExpenseQueryTool())
register_tool(BudgetQueryTool())
register_tool(SalaryQueryTool())
register_tool(InvoiceOCRTool())

# 注册 HR 工具
register_tool(AttendanceQueryTool())
register_tool(TeamAttendanceTool())
register_tool(EmployeeProfileTool())
register_tool(PerformanceReviewTool())
register_tool(RecruitmentTool())

# 注册领导专属工具
register_tool(SmartApprovalTool())
register_tool(DailyBriefingTool())
register_tool(BusinessDashboardTool())
register_tool(TeamInsightTool())
register_tool(AnnouncementTool())
register_tool(CustomerProfileTool())

# 注册合同分析工具
register_tool(ContractAnalysisTool())

# 注册 CRM 客户管理工具
register_tool(GetCustomersTool())
register_tool(GetCustomerDetailTool())
register_tool(CreateCustomerTool())
register_tool(UpdateCustomerTool())
register_tool(AddFollowUpTool())
register_tool(GetFollowUpsTool())
register_tool(UpdateCustomerStageTool())
register_tool(GetSalesPipelineTool())

# 注册合同 CRUD 工具
register_tool(GetContractsTool())
register_tool(CreateContractTool())
register_tool(GetExpiringContractsTool())

# 注册战略分析工具 (Phase 4)
register_tool(DataAttributionTool())
register_tool(StrategySimulationTool())

# ============================================================
# VMD (Virtual Marketing Department) 虚拟市场部行业专属工具
# ============================================================
try:
    from .vmd_content_tools import (
        GenerateApplicationNoteTool,
        GenerateProductManualTool,
        GenerateSocialPostTool,
        GenerateWhitepaperTool,
    )

    register_tool(GenerateProductManualTool())
    register_tool(GenerateWhitepaperTool())
    register_tool(GenerateApplicationNoteTool())
    register_tool(GenerateSocialPostTool())
except ImportError:
    pass

try:
    from .vmd_tender_tools import (
        CheckBidComplianceTool,
        ExtractBidRequirementsTool,
        GenerateBidDocumentTool,
        GenerateDeviationTableTool,
    )

    register_tool(GenerateBidDocumentTool())
    register_tool(GenerateDeviationTableTool())
    register_tool(CheckBidComplianceTool())
    register_tool(ExtractBidRequirementsTool())
except ImportError:
    pass

try:
    from .vmd_sales_tools import (
        GenerateCompetitorComparisonTool,
        GenerateQuotationTemplateTool,
        GenerateSalesScriptTool,
        GenerateTrainingMaterialTool,
    )

    register_tool(GenerateSalesScriptTool())
    register_tool(GenerateCompetitorComparisonTool())
    register_tool(GenerateTrainingMaterialTool())
    register_tool(GenerateQuotationTemplateTool())
except ImportError:
    pass

try:
    from .vmd_synergy_tools import (
        AggregateCustomerFeedbackTool,
        GenerateCompetitorAnalysisTool,
        GenerateMarketResearchTool,
        MonitorIndustryTrendsTool,
    )

    register_tool(MonitorIndustryTrendsTool())
    register_tool(GenerateMarketResearchTool())
    register_tool(GenerateCompetitorAnalysisTool())
    register_tool(AggregateCustomerFeedbackTool())
except ImportError:
    pass

try:
    from .vmd_operation_tools import (
        CustomerLifecycleAnalysisTool,
        GenerateFaqResponseTool,
        GenerateMaintenanceReminderTool,
        GenerateRepurchaseCampaignTool,
    )

    register_tool(GenerateMaintenanceReminderTool())
    register_tool(GenerateFaqResponseTool())
    register_tool(GenerateRepurchaseCampaignTool())
    register_tool(CustomerLifecycleAnalysisTool())
except ImportError:
    pass


def get_tool(name: str) -> BaseTool:
    return TOOL_REGISTRY.get(name)


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
    """Generates the OpenAI tools schema list dynamically"""
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
