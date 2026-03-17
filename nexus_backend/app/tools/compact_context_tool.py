"""
Compact Context Tool — Agent-initiated context compression (P0).

This is a *pseudo-tool*: the LLM "calls" it, but node_execute.py intercepts
the call before any real execution.  The agent passes a summary of the
conversation so far, and the execute node stores it in state for downstream
use, effectively replacing verbose history with a compact digest.
"""

from typing import Any

from app.tools.base_tool import BaseTool
from app.tools.registry import register_tool


@register_tool
class CompactContextTool(BaseTool):
    name = "compact_context"
    description = (
        "当你感觉上下文过长、工具结果冗余、或即将超出 token 限制时，"
        "调用此工具压缩历史上下文。传入一段对之前所有对话和工具调用结果的精炼摘要，"
        "保留关键数据、结论和待办事项。调用后系统会自动用摘要替代冗长历史。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": (
                    "对之前所有对话和工具调用结果的精炼摘要。"
                    "必须保留：关键数据点、已得出的结论、待完成的步骤。"
                ),
            },
        },
        "required": ["summary"],
    }
    category = "system"
    domain = "system"

    async def execute(
        self, arguments: dict[str, Any], context: dict[str, Any] | None = None
    ) -> str:
        # This method should never be reached — node_execute.py intercepts
        # compact_context calls as a pseudo-tool.  If we get here, return
        # a harmless acknowledgement.
        return "[compact_context] 上下文压缩已完成。"
