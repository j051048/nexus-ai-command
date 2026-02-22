"""
Item 16: Notification Center API

Endpoints for managing in-app notifications and notification preferences.
"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.notification_center_service import notification_center_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/notifications", tags=["Notification Center"])


# ─── Request Models ──────────────────────────────────────────

class MarkReadBody(BaseModel):
    notification_ids: list[str] = Field(
        ..., min_length=1, description="要标记已读的通知 ID 列表"
    )


class UpdatePreferencesBody(BaseModel):
    email_enabled: bool | None = None
    push_enabled: bool | None = None
    im_enabled: bool | None = None
    quiet_hours_start: str | None = Field(
        None, description="免打扰开始时间 (HH:MM)"
    )
    quiet_hours_end: str | None = Field(
        None, description="免打扰结束时间 (HH:MM)"
    )
    categories: dict | None = Field(
        None, description="分类通知开关 {approval: bool, system: bool, ...}"
    )


# ─── Endpoints ───────────────────────────────────────────────


@router.get("")
async def get_notifications(
    request: Request,
    unread_only: bool = False,
    type: str | None = None,  # noqa: A002
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
):
    """获取通知列表"""
    try:
        db = getattr(request.state, "db", None)

        notifications = await notification_center_service.get_notifications(
            user_id=user_id,
            unread_only=unread_only,
            type_filter=type,
            limit=min(limit, 100),
            offset=offset,
            db=db,
        )

        return api_success(data=notifications, message="通知列表获取成功")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error getting notifications: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/mark-read")
async def mark_read(
    request: Request,
    body: MarkReadBody,
    user_id: str = Depends(get_current_user_id),
):
    """标记指定通知为已读"""
    try:
        db = getattr(request.state, "db", None)

        count = await notification_center_service.mark_read(
            user_id=user_id,
            notification_ids=body.notification_ids,
            db=db,
        )

        return api_success(
            data={"marked_count": count},
            message=f"已标记 {count} 条通知为已读",
        )
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error marking notifications as read: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/mark-all-read")
async def mark_all_read(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """全部标记已读"""
    try:
        db = getattr(request.state, "db", None)

        count = await notification_center_service.mark_all_read(
            user_id=user_id,
            db=db,
        )

        return api_success(
            data={"marked_count": count},
            message=f"已将 {count} 条通知标记为已读",
        )
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error marking all notifications as read: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/unread-count")
async def get_unread_count(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取未读通知数"""
    try:
        db = getattr(request.state, "db", None)

        count = await notification_center_service.get_unread_count(
            user_id=user_id,
            db=db,
        )

        return api_success(data={"unread_count": count})
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error getting unread count: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/preferences")
async def get_preferences(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取通知偏好设置"""
    try:
        db = getattr(request.state, "db", None)

        preferences = await notification_center_service.get_preferences(
            user_id=user_id,
            db=db,
        )

        return api_success(data=preferences)
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error getting preferences: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/preferences")
async def update_preferences(
    request: Request,
    body: UpdatePreferencesBody,
    user_id: str = Depends(get_current_user_id),
):
    """更新通知偏好设置"""
    try:
        db = getattr(request.state, "db", None)

        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            prefs = await notification_center_service.get_preferences(
                user_id=user_id, db=db,
            )
            return api_success(data=prefs, message="无变更")

        preferences = await notification_center_service.update_preferences(
            user_id=user_id,
            preferences=updates,
            db=db,
        )

        return api_success(data=preferences, message="通知偏好已更新")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error updating preferences: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
