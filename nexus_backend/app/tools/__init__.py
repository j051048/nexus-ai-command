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

# 合同分析工具
from .contract_tools import ContractAnalysisTool

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

# 注册战略分析工具 (Phase 4)
register_tool(DataAttributionTool())
register_tool(StrategySimulationTool())


def get_tool(name: str) -> BaseTool:
    return TOOL_REGISTRY.get(name)


def get_all_tools_schema():
    """Generates the OpenAI tools schema list dynamically"""
    schemas = []
    for tool in TOOL_REGISTRY.values():
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
        )
    return schemas
