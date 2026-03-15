"""
用户 AI 推送偏好 API

管理用户对 AI 主动推送（smart_reminder / insight / recommendation / alert）的反馈与偏好。
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.user_preference_service import user_preference_service

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/notification-preferences",
    tags=["AI Notification Preferences"],
)


# ─── Request / Response Models ──────────────────────────────


class FeedbackBody(BaseModel):
    notification_type: str = Field(
        ..., description="通知类型: smart_reminder | insight | recommendation | alert"
    )
    action: str = Field(
        ..., description="用户行为: clicked | dismissed | ignored | muted"
    )


class UpdatePreferencesBody(BaseModel):
    active_hours_start: int | None = Field(None, ge=0, le=23)
    active_hours_end: int | None = Field(None, ge=0, le=23)
    daily_notification_limit: int | None = Field(None, ge=1, le=100)
    muted_types: list[str] | None = None


# ─── Endpoints ──────────────────────────────────────────────


@router.post("/feedback")
async def record_feedback(
    body: FeedbackBody,
    user_id: str = Depends(get_current_user_id),
):
    """记录用户对 AI 推送通知的反馈"""
    try:
        valid_actions = {"clicked", "dismissed", "ignored", "muted"}
        if body.action not in valid_actions:
            raise api_error(
                ErrorCode.VALIDATION_ERROR,
                f"action 必须是 {valid_actions} 之一",
            )

        await user_preference_service.record_feedback(
            user_id=user_id,
            notification_type=body.notification_type,
            action=body.action,
        )

        return api_success(data={"recorded": True}, message="反馈已记录")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error recording feedback: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("")
async def get_preferences(
    user_id: str = Depends(get_current_user_id),
):
    """获取用户 AI 推送偏好摘要"""
    try:
        prefs = await user_preference_service.get_user_preferences(user_id)
        return api_success(data=prefs)
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error getting AI notification preferences: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("")
async def update_preferences(
    body: UpdatePreferencesBody,
    user_id: str = Depends(get_current_user_id),
):
    """更新用户 AI 推送偏好设置"""
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            prefs = await user_preference_service.get_user_preferences(user_id)
            return api_success(data=prefs, message="无变更")

        prefs = await user_preference_service.update_settings(user_id, updates)
        return api_success(data=prefs, message="偏好已更新")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error updating AI notification preferences: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
