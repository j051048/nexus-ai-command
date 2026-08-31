"""
save_memory_tool — Agent 主动记忆写入工具。

让 Agent 在对话过程中可以主动保存用户偏好、事实、明确指令到长期记忆库，
而不必等到对话结束后由 persist_result 被动提取。
"""

import logging
from typing import Any

from app.tools._shared import safe_tool_error
from app.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class SaveMemoryTool(BaseTool):
    """主动保存一条用户记忆到长期记忆库。"""

    domain = "system"
    requires_org_id = False

    @property
    def name(self) -> str:
        return "save_memory"

    @property
    def description(self) -> str:
        return (
            "保存一条用户记忆到长期记忆库，包括偏好、事实或用户明确要求记住的信息。\n"
            "使用场景:\n"
            '- 用户明确说"记住"、"以后都"、"我喜欢"\n'
            "- 推理过程中发现重要的用户偏好或事实\n"
            "- 用户纠正了你的理解, 需要记录正确信息\n"
            "不要用于保存临时信息或当前对话的中间结果。"
        )

    @property
    def examples(self) -> list[dict]:
        return [
            {
                "input": {
                    "key": "report_format_preference",
                    "value": "用户偏好用表格形式展示数据，不喜欢纯文字",
                    "category": "preference",
                    "importance": 0.8,
                },
                "output_summary": "保存用户的报告格式偏好到长期记忆",
            },
            {
                "input": {
                    "key": "main_client_name",
                    "value": "用户的主要客户是华为终端",
                    "category": "fact",
                    "importance": 0.6,
                },
                "output_summary": "保存用户的关键客户信息",
            },
        ]

    @property
    def related_tools(self) -> list[str]:
        return ["search_long_term_memory"]

    @property
    def gotchas(self) -> str:
        return "不要保存临时或一次性信息；key 必须用英文蛇形命名；importance 范围 0.0-1.0，超出会被自动截断。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "记忆标识键，简短英文蛇形命名，如 report_format_preference",
                },
                "value": {
                    "type": "string",
                    "description": "记忆内容，用自然语言描述",
                },
                "category": {
                    "type": "string",
                    "enum": ["preference", "fact", "explicit_memory"],
                    "description": "记忆类型：preference=偏好习惯, fact=事实信息, explicit_memory=用户明确要求记住的",
                },
                "importance": {
                    "type": "number",
                    "description": "重要性 0.0-1.0，身份/核心偏好=0.8-1.0，工作习惯=0.5-0.7，一般事实=0.3-0.4",
                },
            },
            "required": ["key", "value"],
        }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] | None = None
    ) -> str:
        from app.services.conversation_memory_service import conversation_memory_service

        key = args["key"]
        value = args["value"]
        category = args.get("category", "preference")
        importance = args.get("importance", 0.7)
        org_id = (config or {}).get("org_id")

        # Clamp importance to valid range
        importance = max(0.0, min(1.0, float(importance)))

        try:
            await conversation_memory_service.save_memory(
                user_id=user_id,
                key=key,
                value=value,
                category=category,
                importance=importance,
                org_id=org_id,
            )
            logger.info(
                f"[SaveMemory] Agent actively saved: key={key}, category={category}, importance={importance}"
            )
            snippet = value[:80] + ("…" if len(value) > 80 else "")
            return self.format_result(
                data={"key": key, "category": category, "importance": importance},
                summary=f"✅ 已记住: {key} = {snippet}",
            )
        except Exception as e:
            logger.warning(f"[SaveMemory] Failed to save memory: {e}")
            return self.format_result(data={}, summary=safe_tool_error(e, "⚠️ 记忆保存"))
