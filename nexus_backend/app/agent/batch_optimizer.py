"""
P1-1: 批量工具优化器
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# 支持批量的工具映射
BATCH_TOOLS = {
    "get_customer": "get_customers_batch",
    "get_contract": "get_contracts_batch",
    "get_sales_lead": "get_sales_leads_batch"
}


class BatchOptimizer:
    """批量操作优化器"""

    def can_batch(self, tool_calls: list[dict]) -> bool:
        """检查是否可以批量化"""
        if len(tool_calls) < 2:
            return False

        # 检查是否都是同一个工具
        tool_names = [call["tool"] for call in tool_calls]
        if len(set(tool_names)) != 1:
            return False

        # 检查工具是否支持批量
        return tool_names[0] in BATCH_TOOLS

    def merge_to_batch(self, tool_calls: list[dict]) -> dict:
        """合并为批量调用"""
        tool_name = tool_calls[0]["tool"]
        batch_tool = BATCH_TOOLS[tool_name]

        # 提取所有 ID
        ids = [call["args"].get("id") if call["args"].get("id") is not None
               else call["args"].get("customer_id")
               for call in tool_calls]

        return {
            "tool": batch_tool,
            "args": {"ids": ids}
        }

    async def optimize(self, tool_calls: list[dict]) -> list[dict]:
        """优化工具调用列表"""
        # 按工具名分组
        grouped = {}
        for call in tool_calls:
            tool = call["tool"]
            if tool not in grouped:
                grouped[tool] = []
            grouped[tool].append(call)

        # 尝试批量化
        optimized = []
        for tool, calls in grouped.items():
            if len(calls) > 1 and tool in BATCH_TOOLS:
                batch_call = self.merge_to_batch(calls)
                optimized.append(batch_call)
            else:
                optimized.extend(calls)

        return optimized


# 全局实例
batch_optimizer = BatchOptimizer()
