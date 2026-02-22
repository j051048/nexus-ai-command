"""
Item 16: Notification Center Service

Manages in-app notification center with read/unread tracking,
preference settings, and quiet hours support.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)

# Valid notification types
VALID_NOTIFICATION_TYPES = {"info", "success", "warning", "error", "approval", "system"}

# Default notification preferences
DEFAULT_PREFERENCES: dict[str, Any] = {
    "email_enabled": True,
    "push_enabled": True,
    "im_enabled": True,
    "quiet_hours_start": None,
    "quiet_hours_end": None,
    "categories": {
        "approval": True,
        "system": True,
        "ai": True,
        "report": True,
    },
}


class NotificationCenterService:
    """站内消息中心服务"""

    # ─── 通知 CRUD ───────────────────────────────────────────────

    async def create_notification(
        self,
        user_id: str,
        title: str,
        body: str | None = None,
        type: str = "info",  # noqa: A002
        action_url: str | None = None,
        org_id: str | None = None,
        db: Any = None,
    ) -> dict:
        """创建站内通知"""
        client = db or supabase
        if not client:
            raise RuntimeError("数据库连接不可用")

        if type not in VALID_NOTIFICATION_TYPES:
            type = "info"  # noqa: A001

        data = {
            "user_id": user_id,
            "title": title,
            "body": body or "",
            "type": type,
            "action_url": action_url,
            "is_read": False,
            "created_at": datetime.now(UTC).isoformat(),
        }

        if org_id:
            data["organization_id"] = org_id

        result = await client.table("notifications").insert(data).execute()

        if not result.data:
            raise RuntimeError("创建通知失败")

        created = result.data[0] if isinstance(result.data, list) else result.data
        logger.info(f"Created notification for user {user_id}: {title[:50]}")
        return created

    async def get_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        type_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
        db: Any = None,
    ) -> list[dict]:
        """获取通知列表"""
        client = db or supabase
        if not client:
            return []

        query = (
            client.table("notifications")
            .select("*")
            .eq("user_id", user_id)
        )

        if unread_only:
            query = query.eq("is_read", False)

        if type_filter and type_filter in VALID_NOTIFICATION_TYPES:
            query = query.eq("type", type_filter)

        result = (
            await query
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        return result.data or []

    async def mark_read(
        self,
        user_id: str,
        notification_ids: list[str],
        db: Any = None,
    ) -> int:
        """标记指定通知为已读"""
        client = db or supabase
        if not client:
            return 0

        if not notification_ids:
            return 0

        result = (
            await client.table("notifications")
            .update({"is_read": True})
            .eq("user_id", user_id)
            .in_("id", notification_ids)
            .execute()
        )

        count = len(result.data) if result.data else 0
        logger.info(f"Marked {count} notifications as read for user {user_id}")
        return count

    async def mark_all_read(
        self,
        user_id: str,
        db: Any = None,
    ) -> int:
        """全部标记已读"""
        client = db or supabase
        if not client:
            return 0

        result = (
            await client.table("notifications")
            .update({"is_read": True})
            .eq("user_id", user_id)
            .eq("is_read", False)
            .execute()
        )

        count = len(result.data) if result.data else 0
        logger.info(f"Marked all ({count}) notifications as read for user {user_id}")
        return count

    async def get_unread_count(
        self,
        user_id: str,
        db: Any = None,
    ) -> int:
        """获取未读数"""
        client = db or supabase
        if not client:
            return 0

        try:
            result = (
                await client.table("notifications")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .eq("is_read", False)
                .execute()
            )

            # PostgREST returns count in the response
            if hasattr(result, "count") and result.count is not None:
                return result.count

            # Fallback: count the returned data
            return len(result.data) if result.data else 0
        except Exception as e:
            logger.warning(f"Failed to get unread count: {e}")
            return 0

    # ─── 通知偏好 ────────────────────────────────────────────────

    async def get_preferences(
        self,
        user_id: str,
        db: Any = None,
    ) -> dict:
        """获取通知偏好设置"""
        client = db or supabase
        if not client:
            return {**DEFAULT_PREFERENCES, "user_id": user_id}

        try:
            result = (
                await client.table("notification_preferences")
                .select("*")
                .eq("user_id", user_id)
                .maybe_single()
                .execute()
            )

            if result.data:
                return result.data

            # Return defaults if no preferences exist
            return {**DEFAULT_PREFERENCES, "user_id": user_id}
        except Exception as e:
            logger.warning(f"Failed to get notification preferences: {e}")
            return {**DEFAULT_PREFERENCES, "user_id": user_id}

    async def update_preferences(
        self,
        user_id: str,
        preferences: dict[str, Any],
        db: Any = None,
    ) -> dict:
        """更新通知偏好设置（upsert）"""
        client = db or supabase
        if not client:
            raise RuntimeError("数据库连接不可用")

        # Sanitize input: only allow known preference keys
        allowed_keys = {
            "email_enabled", "push_enabled", "im_enabled",
            "quiet_hours_start", "quiet_hours_end", "categories",
        }
        sanitized = {k: v for k, v in preferences.items() if k in allowed_keys}
        sanitized["user_id"] = user_id
        sanitized["updated_at"] = datetime.now(UTC).isoformat()

        # Check if preferences exist
        existing = (
            await client.table("notification_preferences")
            .select("id")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

        if existing.data:
            # Update existing
            result = (
                await client.table("notification_preferences")
                .update(sanitized)
                .eq("user_id", user_id)
                .execute()
            )
        else:
            # Insert new preferences with defaults merged
            insert_data = {**DEFAULT_PREFERENCES, **sanitized}
            result = (
                await client.table("notification_preferences")
                .insert(insert_data)
                .execute()
            )

        if not result.data:
            raise RuntimeError("更新通知偏好失败")

        saved = result.data[0] if isinstance(result.data, list) else result.data
        logger.info(f"Updated notification preferences for user {user_id}")
        return saved

    # ─── 批量通知创建（内部使用）─────────────────────────────────

    async def notify_users(
        self,
        user_ids: list[str],
        title: str,
        body: str | None = None,
        type: str = "info",  # noqa: A002
        action_url: str | None = None,
        org_id: str | None = None,
        db: Any = None,
    ) -> int:
        """批量创建通知（给多个用户）"""
        client = db or supabase
        if not client or not user_ids:
            return 0

        now = datetime.now(UTC).isoformat()
        rows = []
        for uid in user_ids:
            row: dict[str, Any] = {
                "user_id": uid,
                "title": title,
                "body": body or "",
                "type": type if type in VALID_NOTIFICATION_TYPES else "info",
                "action_url": action_url,
                "is_read": False,
                "created_at": now,
            }
            if org_id:
                row["organization_id"] = org_id
            rows.append(row)

        try:
            result = await client.table("notifications").insert(rows).execute()
            count = len(result.data) if result.data else 0
            logger.info(f"Created {count} notifications for {len(user_ids)} users")
            return count
        except Exception as e:
            logger.error(f"Batch notification creation failed: {e}")
            return 0


# Global service instance
notification_center_service = NotificationCenterService()
