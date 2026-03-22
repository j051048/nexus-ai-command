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
    domain = "system"

    name = "ask_user"
    description = (
        "向用户提出澄清问题，在继续执行之前获取用户输入或确认。"
        "当不确定用户意图、需要用户选择方案、或需要补充信息时调用。"
        "提供问题文本和可选的预设选项列表。"
    )
    examples = [
        {"input": {"question": "您希望按哪个维度汇总销售数据？", "options": ["按月汇总", "按季度汇总", "按客户汇总"]}, "output_summary": "向用户展示选项列表并等待选择"},
        {"input": {"question": "请确认您要删除的是哪个客户的记录？", "context": "搜索结果中有多个同名客户"}, "output_summary": "带上下文说明向用户提出澄清问题"},
    ]
    related_tools = ["save_memory"]
    gotchas = "此工具为伪工具，不会真正执行，由前端拦截处理；不要在用户意图明确时滥用此工具。"
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
            "fields": {
                "type": "array",
                "description": "表单字段列表。设置此参数时前端会渲染结构化表单而非简单问答。",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "字段标识符"},
                        "label": {"type": "string", "description": "字段显示标签"},
                        "type": {
                            "type": "string",
                            "enum": ["text", "number", "email", "select", "date", "textarea", "checkbox"],
                            "description": "字段类型",
                        },
                        "required": {"type": "boolean", "description": "是否必填"},
                        "default_value": {"type": "string", "description": "AI预填的默认值"},
                        "options": {"type": "array", "items": {"type": "string"}, "description": "select类型的选项列表"},
                        "placeholder": {"type": "string", "description": "占位提示文本"},
                        "step": {"type": "integer", "description": "多步骤表单的步骤号(从1开始)"},
                    },
                    "required": ["name", "label", "type"],
                },
            },
        },
        "required": ["question"],
    }
    requires_confirmation = False  # This is a UI interaction, not a sensitive action

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        """This tool should never actually execute — it's intercepted by execute_node."""
        return "[ask_user] 此工具被拦截用于前端交互，不应直接执行。"
