from .base_tool import BaseTool
from .tender_tool import TenderAnalysisTool
from .battlecard_tool import BattlecardTool
from typing import Dict

# Registry of all available tools
# P1: Strategy Pattern Registry
TOOL_REGISTRY: Dict[str, BaseTool] = {}

def register_tool(tool: BaseTool):
    TOOL_REGISTRY[tool.name] = tool

from .approval_tools import ApprovalTool, RejectTool, PendingApprovalsTool
from .operational_tools import PerformanceReportTool, CompanyStatsTool, KnowledgeBaseTool, AwardBadgeTool
from .project_tools import ProjectListTool, CreateEventTool, CreateProjectTool

# OA 办公自动化工具
from .oa_tools import (
    LeaveRequestTool, 
    LeaveQueryTool, 
    MeetingBookingTool, 
    TaskAssignmentTool,
    WorkHandoverTool
)

# 财务管理工具
from .finance_tools import (
    ExpenseClaimTool,
    ExpenseQueryTool,
    BudgetQueryTool,
    SalaryQueryTool,
    InvoiceOCRTool
)

# HR 人力资源工具
from .hr_tools import (
    AttendanceQueryTool,
    TeamAttendanceTool,
    EmployeeProfileTool,
    PerformanceReviewTool,
    RecruitmentTool
)

# 领导专属工具
from .boss_tools import (
    SmartApprovalTool,
    DailyBriefingTool,
    BusinessDashboardTool,
    TeamInsightTool,
    AnnouncementTool
)

# Registering Tools
register_tool(TenderAnalysisTool())
register_tool(BattlecardTool())
register_tool(ApprovalTool())
register_tool(RejectTool())
register_tool(PendingApprovalsTool())
register_tool(PerformanceReportTool())
register_tool(CompanyStatsTool())
register_tool(KnowledgeBaseTool())
register_tool(AwardBadgeTool())
register_tool(ProjectListTool())
register_tool(CreateEventTool())
register_tool(CreateProjectTool())

# 注册 OA 工具
register_tool(LeaveRequestTool())
register_tool(LeaveQueryTool())
register_tool(MeetingBookingTool())
register_tool(TaskAssignmentTool())
register_tool(WorkHandoverTool())

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

def get_tool(name: str) -> BaseTool:
    return TOOL_REGISTRY.get(name)

def get_all_tools_schema():
    """Generates the OpenAI tools schema list dynamically"""
    schemas = []
    for tool in TOOL_REGISTRY.values():
        schemas.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
        })
    return schemas
