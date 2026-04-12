"""公告发布工具"""

import logging
from typing import Any

from ..base_tool import BaseTool
from ..boss_shared import _get_client

logger = logging.getLogger(__name__)


class AnnouncementTool(BaseTool):
    """公告发布工具"""

    name = "publish_announcement"
    description = "发布全员或部门级公告通知。当领导说'发个通知'、'通知全员'时调用。注意：给特定个人发消息请用 send_notification。"
    required_role = "boss"
    domain = "admin"
    examples = [
        {
            "input": {
                "title": "节假日安排",
                "content": "五一放假三天",
                "target": "all",
                "priority": "normal",
            },
            "output_summary": "向全员发布节假日通知",
        },
        {
            "input": {
                "title": "紧急通知",
                "content": "系统维护",
                "target": "managers",
                "priority": "urgent",
            },
            "output_summary": "向管理层发布紧急维护通知",
        },
    ]
    related_tools = ["send_notification", "smart_approve"]
    gotchas = "全员通知或紧急通知需要人工确认后才能发送。发布后不可撤回。通知按50条一批写入数据库。"

    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "公告标题"},
            "content": {"type": "string", "description": "公告内容"},
            "target": {
                "type": "string",
                "enum": ["all", "managers", "sales", "department"],
                "description": "通知对象",
            },
            "priority": {
                "type": "string",
                "enum": ["normal", "important", "urgent"],
                "description": "优先级",
            },
        },
        "required": ["title", "content"],
    }

    def check_confirmation(
        self, args: dict[str, Any], system_confirmed: bool = False
    ) -> tuple[str | None, str]:
        """Only require confirmation for all-staff or urgent announcements."""
        target = args.get("target", "all")
        priority = args.get("priority", "normal")
        if target == "all" or priority == "urgent":
            if system_confirmed:
                return None, ""
            scope = "全员" if target == "all" else "紧急"
            return (
                f"⚠️ 操作需要确认:\n🔒 {scope}通知将发送给所有目标用户，发布后不可撤回。\n请确认后再执行。",
                "irreversible",
            )
        return None, ""

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        title = args.get("title")
        content = args.get("content")
        target = args.get("target", "all")
        priority = args.get("priority", "normal")

        client = _get_client(config)
        org_id = config.get("org_id") if config else None
        # 获取目标用户
        if target == "all":
            users_query = client.table("users").select("id, name")
            if org_id:
                users_query = users_query.eq("organization_id", org_id)
            users_res = await users_query.execute()
        elif target == "managers":
            users_query = (
                client.table("users")
                .select("id, name")
                .in_("role", ["manager", "founder"])
            )
            if org_id:
                users_query = users_query.eq("organization_id", org_id)
            users_res = await users_query.execute()
        else:
            users_query = client.table("users").select("id, name")
            if org_id:
                users_query = users_query.eq("organization_id", org_id)
            users_res = await users_query.execute()

        users = users_res.data or []

        # Batch insert in-app notifications via NotificationCenterService
        priority_icons = {"normal": "📢", "important": "⚠️", "urgent": "🚨"}
        icon = priority_icons.get(priority, "📢")
        notification_type = "info" if priority == "normal" else "warning"
        user_ids = [u["id"] for u in users]
        try:
            from app.services.notification_center_service import (
                notification_center_service,
            )

            await notification_center_service.notify_users(
                user_ids=user_ids,
                title=f"{icon} {title}",
                body=content,
                type=notification_type,
                org_id=org_id,
                db=client,
            )
        except Exception as e:
            logger.warning(f"Failed to batch insert announcement notifications: {e}")

        # Multi-channel notification for announcements
        try:
            from app.services.notification_service import (
                Notification,
                NotificationChannel,
                NotificationPriority,
                notification_service,
            )

            priority_map = {
                "normal": NotificationPriority.NORMAL,
                "important": NotificationPriority.HIGH,
                "urgent": NotificationPriority.URGENT,
            }
            notif_priority = priority_map.get(priority, NotificationPriority.NORMAL)

            # Send to all available external channels (wecom/dingtalk/feishu)
            for channel in notification_service.get_available_channels():
                if (
                    channel != NotificationChannel.IN_APP
                ):  # Already handled by batch insert
                    try:
                        await notification_service.send(
                            Notification(
                                title=f"{icon} {title}",
                                content=content,
                                target_user_id="all",
                                channel=channel,
                                priority=notif_priority,
                                metadata={"announcement": True, "target_scope": target},
                            )
                        )
                    except Exception as e:
                        logger.warning(f"Announcement push to {channel} failed: {e}")
        except Exception as e:
            logger.warning(f"Multi-channel announcement push failed: {e}")

        target_names = {"all": "全员", "managers": "管理层", "sales": "销售团队"}

        return f"""✅ 公告已发布！

**公告详情**
- 标题: {title}
- 内容: {content[:50]}{"..." if len(content) > 50 else ""}
- 对象: {target_names.get(target, target)}（{len(users)}人）
- 优先级: {priority}

📧 已推送给 {len(users)} 名员工
📊 您可以稍后问我「公告阅读情况」查看已读统计
"""
