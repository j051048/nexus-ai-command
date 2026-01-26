from .base_tool import BaseTool
from .tender_tool import TenderAnalysisTool
from .battlecard_tool import BattlecardTool
from typing import Dict

# Registry of all available tools
# P1: Strategy Pattern Registry
TOOL_REGISTRY: Dict[str, BaseTool] = {}

def register_tool(tool: BaseTool):
    TOOL_REGISTRY[tool.name] = tool

# Registering Tools
register_tool(TenderAnalysisTool())
register_tool(BattlecardTool())

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
