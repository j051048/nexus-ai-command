"""
P1-7: ask_user pseudo-tool — allows the agent to proactively ask the user
a clarifying question before proceeding.

This is NOT a real tool that calls an API. Instead, the execute_node
detects this tool call and emits an SSE event that triggers a UI prompt.
The user's answer is sent back as a new message in the next request.
"""

from typing import Any

from app.tools.base_tool import BaseTool


class AskUserTool(BaseTool):
    """Agent 主动向用户提问的伪工具。

    当 Agent 需要用户提供额外信息或确认偏好时调用此工具。
    execute_node 会拦截此调用并转换为 SSE 事件发送到前端。
    """

    name = "ask_user"
    description = (
        "向用户提出一个澄清问题，在继续执行之前获取用户输入。"
        "当你不确定用户意图、需要用户选择方案、或需要额外信息时使用此工具。"
        "提供 question 字段（问题文本）和可选的 options 字段（选项列表）。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "要向用户提出的问题",
            },
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "可选的预设选项列表，用户也可以自由输入",
            },
            "context": {
                "type": "string",
                "description": "问题的上下文说明，帮助用户理解为什么需要这个信息",
            },
        },
        "required": ["question"],
    }
    requires_confirmation = False  # This is a UI interaction, not a sensitive action

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        """This tool should never actually execute — it's intercepted by execute_node."""
        return "[ask_user] 此工具被拦截用于前端交互，不应直接执行。"
