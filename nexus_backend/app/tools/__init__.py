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
