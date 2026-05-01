"""
用户偏好管理工具
暴露 UserPreferenceService 给 Agent，支持查看和更新用户个人偏好。
"""

import logging
from typing import Any

from app.tools._shared import safe_tool_error

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class GetUserPreferencesTool(BaseTool):
    """查看用户偏好设置"""

    name = "get_user_preferences"
    description = (
        "查询当前用户的个人偏好设置，包括通知活跃时段、每日通知上限、已静音的通知类型和接受率统计。"
        "当用户说'查看我的设置'、'我的偏好'、'通知设置'时调用。"
    )
    examples = [
        {
            "input": {},
            "output_summary": "返回用户的完整偏好设置，包括活跃时段、通知上限等",
        },
    ]
    related_tools = ["update_user_preferences"]
    gotchas = ""

    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    domain = "schedule"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        from app.services.user_preference_service import user_preference_service

        try:
            prefs = await user_preference_service.get_user_preferences(user_id)

            result = {
                "active_hours": f"{prefs['active_hours'][0]}:00 - {prefs['active_hours'][1]}:00",
                "daily_notification_limit": prefs["daily_limit"],
                "muted_types": (
                    prefs["muted_types"] if prefs["muted_types"] else "无（全部开启）"
                ),
                "notification_stats": (
                    prefs["type_stats"] if prefs["type_stats"] else "暂无统计数据"
                ),
            }

            return self.format_result(
                data=result,
                summary="已获取用户偏好设置",
            )

        except Exception as e:
            logger.error(f"[PreferenceTool] Get failed: {e}")
            return self.format_result(data={}, summary=safe_tool_error(e, "获取偏好设置"))


class UpdateUserPreferencesTool(BaseTool):
    """更新用户偏好设置"""

    name = "update_user_preferences"
    description = (
        "更新当前用户的个人偏好设置，可修改通知活跃时段、每日通知上限、静音或取消静音特定通知类型。"
        "当用户说'修改我的设置'、'不要在下班后通知我'、'每天最多通知3次'、"
        "'关掉某类通知'时调用。"
    )
    examples = [
        {
            "input": {"active_hours_start": 9, "active_hours_end": 18},
            "output_summary": "将通知活跃时段设为9:00-18:00",
        },
        {
            "input": {"daily_notification_limit": 5},
            "output_summary": "将每日通知上限设为5条",
        },
        {
            "input": {"mute_type": "system_alert"},
            "output_summary": "静音系统告警类通知",
        },
    ]
    related_tools = ["get_user_preferences"]
    gotchas = "至少需要传一个参数才能执行更新；active_hours_start 和 active_hours_end 可以单独设置；mute_type 和 unmute_type 在同一次调用中不要同时传相同类型。"

    parameters = {
        "type": "object",
        "properties": {
            "active_hours_start": {
                "type": "integer",
                "description": "通知活跃时段开始小时(0-23)，如9表示早上9点",
                "minimum": 0,
                "maximum": 23,
            },
            "active_hours_end": {
                "type": "integer",
                "description": "通知活跃时段结束小时(0-23)，如18表示下午6点",
                "minimum": 0,
                "maximum": 23,
            },
            "daily_notification_limit": {
                "type": "integer",
                "description": "每日通知上限数量",
                "minimum": 0,
                "maximum": 50,
            },
            "mute_type": {
                "type": "string",
                "description": "要静音的通知类型，如: approval, task_reminder, system_alert",
            },
            "unmute_type": {
                "type": "string",
                "description": "要取消静音的通知类型",
            },
        },
        "required": [],
    }

    domain = "schedule"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        from app.services.user_preference_service import user_preference_service

        try:
            updates = {}

            if "active_hours_start" in args:
                updates["active_hours_start"] = args["active_hours_start"]
            if "active_hours_end" in args:
                updates["active_hours_end"] = args["active_hours_end"]
            if "daily_notification_limit" in args:
                updates["daily_notification_limit"] = args["daily_notification_limit"]

            # 处理静音/取消静音
            if args.get("mute_type") or args.get("unmute_type"):
                current = await user_preference_service.get_user_preferences(user_id)
                muted = list(current.get("muted_types", []))

                if args.get("mute_type") and args["mute_type"] not in muted:
                    muted.append(args["mute_type"])
                if args.get("unmute_type") and args["unmute_type"] in muted:
                    muted.remove(args["unmute_type"])

                updates["muted_types"] = muted

            if not updates:
                return self.format_result(
                    data={},
                    summary="未指定要更新的设置项。可更新: active_hours_start, active_hours_end, daily_notification_limit, mute_type, unmute_type",
                )

            result = await user_preference_service.update_settings(user_id, updates)

            updated_data = {
                "active_hours": f"{result['active_hours'][0]}:00 - {result['active_hours'][1]}:00",
                "daily_limit": result["daily_limit"],
                "muted_types": (
                    result["muted_types"] if result["muted_types"] else "无"
                ),
            }
            return self.format_result(
                data=updated_data,
                summary="✅ 偏好设置已更新",
            )

        except Exception as e:
            logger.error(f"[PreferenceTool] Update failed: {e}")
            return self.format_result(data={}, summary=safe_tool_error(e, "更新偏好设置"))
