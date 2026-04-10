"""
Skills 动态加载机制
根据场景按需加载工具，优化上下文使用
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# 场景到工具的映射
SCENE_TOOL_MAP = {
    "sales": [
        "crm_tools",
        "vmd_sales_tools",
        "battlecard_tool",
        "report_tools",
        "chart_generation_tool",
        "export_tools",
    ],
    "tender": [
        "tender_tool",
        "vmd_tender_tools",
        "bidding_tool",
        "contract_tools",
        "export_tools",
    ],
    "analysis": [
        "data_analysis_tools",
        "chart_generation_tool",
        "report_tools",
        "export_tools",
        "ai_insight_tools",
    ],
    "hr": [
        "hr_tools",
        "attendance_tools",
        "organization_tools",
    ],
    "finance": [
        "finance_tools",
        "expense_tools",
        "contract_crud_tools",
        "export_tools",
    ],
    "project": [
        "project_tools",
        "vmd_operation_tools",
        "workflow_tools",
        "agent_task_tools",
    ],
}

# 热工具（高频使用，始终加载）
HOT_TOOLS = [
    "web_search_tool",
    "load_knowledge_tool",
    "save_memory_tool",
    "ask_user_tool",
]


def get_tools_for_scene(scene_code: str) -> list[str]:
    """根据场景获取需要加载的工具列表

    Args:
        scene_code: 场景代码（如 sales, tender, analysis）

    Returns:
        工具模块名列表
    """
    tools = HOT_TOOLS.copy()

    if scene_code in SCENE_TOOL_MAP:
        tools.extend(SCENE_TOOL_MAP[scene_code])
    else:
        # 未知场景，加载常用工具
        tools.extend(["crm_tools", "report_tools", "chart_generation_tool"])

    return list(set(tools))  # 去重


def load_tools_dynamically(tool_names: list[str]) -> list[Any]:
    """动态加载工具实例

    Args:
        tool_names: 工具模块名列表

    Returns:
        工具实例列表
    """
    from importlib import import_module

    loaded_tools = []

    for tool_name in tool_names:
        try:
            module = import_module(f"app.tools.{tool_name}")
            # 获取模块中所有的 tool 函数
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if callable(attr) and hasattr(attr, "name"):  # LangChain tool
                    loaded_tools.append(attr)
                    logger.debug(f"加载工具: {tool_name}.{attr_name}")
        except Exception as e:
            logger.warning(f"加载工具 {tool_name} 失败: {e}")

    logger.info(f"动态加载了 {len(loaded_tools)} 个工具")
    return loaded_tools


def get_scene_from_context(
    messages: list[dict] | None = None, agent_code: str = ""
) -> str:
    """从上下文推断场景

    Args:
        messages: 对话历史
        agent_code: Agent 代码

    Returns:
        场景代码
    """
    # 从 agent_code 推断
    if agent_code:
        if "sales" in agent_code.lower():
            return "sales"
        elif "tender" in agent_code.lower():
            return "tender"
        elif "hr" in agent_code.lower():
            return "hr"
        elif "finance" in agent_code.lower():
            return "finance"

    # 从消息内容推断（简单关键词匹配）
    if messages:
        last_msg = messages[-1].get("content", "").lower() if messages else ""
        if any(kw in last_msg for kw in ["客户", "销售", "线索", "商机"]):
            return "sales"
        elif any(kw in last_msg for kw in ["招标", "投标", "标书"]):
            return "tender"
        elif any(kw in last_msg for kw in ["分析", "报表", "图表", "数据"]):
            return "analysis"

    return "sales"  # 默认场景
