"""
Compact Context Tool — Agent-initiated context compression (P0).

This is a *pseudo-tool*: the LLM "calls" it, but node_execute.py intercepts
the call before any real execution.  The agent passes a summary of the
conversation so far, and the execute node stores it in state for downstream
use, effectively replacing verbose history with a compact digest.
"""

from typing import Any

from app.tools.base_tool import BaseTool


class CompactContextTool(BaseTool):
    name = "compact_context"
    description = (
        "压缩对话历史上下文，用精炼摘要替代冗长的历史消息和工具调用结果。"
        "当上下文过长、工具结果冗余或即将超出令牌限制时调用。"
        "传入的摘要需保留关键数据、结论和待办事项。"
    )
    examples = [
        {
            "input": {"summary": "用户查询了本月销售数据，共3个客户成交，总金额12万元。待办：跟进客户A的续约。"},
            "output_summary": "用摘要替代之前的冗长对话历史",
        },
    ]
    related_tools = ["load_knowledge"]
    gotchas = "此工具为伪工具，由系统拦截处理；摘要必须保留关键数据点和待完成步骤，否则后续对话会丢失上下文。"
    parameters = {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": (
                    "对之前所有对话和工具调用结果的精炼摘要。" "必须保留：关键数据点、已得出的结论、待完成的步骤。"
                ),
            },
        },
        "required": ["summary"],
    }
    category = "system"
    domain = "system"

    async def execute(self, arguments: dict[str, Any], context: dict[str, Any] | None = None) -> str:
        # This method should never be reached — node_execute.py intercepts
        # compact_context calls as a pseudo-tool.  If we get here, return
        # a harmless acknowledgement.
        return "[compact_context] 上下文压缩已完成。"

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        return await self.execute(args)
