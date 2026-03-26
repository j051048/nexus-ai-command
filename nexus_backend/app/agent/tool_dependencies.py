"""
工具依赖管理 - 提升 Agent 智能到 8.5 分
"""

import logging
from typing import Dict, List, Set

logger = logging.getLogger(__name__)

# 工具依赖关系图
TOOL_DEPENDENCIES: Dict[str, List[str]] = {
    "create_order": ["get_customer", "check_inventory"],
    "send_invoice": ["create_order"],
    "approve_payment": ["get_invoice", "check_balance"],
    "create_contract": ["get_customer", "get_template"],
    "send_email": ["get_user_email"]
}


class ToolDependencyManager:
    """工具依赖管理器"""

    def get_dependencies(self, tool_name: str) -> List[str]:
        """获取工具的依赖"""
        return TOOL_DEPENDENCIES.get(tool_name, [])

    def resolve_execution_order(self, tools: List[str]) -> List[str]:
        """解析执行顺序（拓扑排序）"""
        visited: Set[str] = set()
        result: List[str] = []

        def dfs(tool: str):
            if tool in visited:
                return
            visited.add(tool)

            for dep in self.get_dependencies(tool):
                dfs(dep)

            result.append(tool)

        for tool in tools:
            dfs(tool)

        return result


# 全局实例
tool_dependency_manager = ToolDependencyManager()
