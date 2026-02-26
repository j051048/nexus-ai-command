"""Web Push 推送通知 API 端点"""

import logging

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.models.schemas import PushSubscribeRequest, PushUnsubscribeRequest
from app.services.push_notification_service import push_notification_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/push", tags=["Push Notifications"])


@router.get("/vapid-key")
async def get_vapid_key():
    """
    获取 VAPID 公钥（公开端点，无需认证）。
    前端用此公钥向浏览器 PushManager 订阅推送。
    """
    key = push_notification_service.vapid_public_key
    if not key:
        return api_success(data={"vapid_key": None, "enabled": False})
    return api_success(data={"vapid_key": key, "enabled": True})


@router.post("/subscribe")
async def subscribe(
    body: PushSubscribeRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    注册推送订阅。
    前端将 PushManager.subscribe() 返回的 subscription 对象发送到此端点。
    """
    try:
        subscription = body.subscription.model_dump()
        org_id = getattr(request.state, "org_id", None)
        user_agent = request.headers.get("user-agent")
        db = getattr(request.state, "db", None)

        result = await push_notification_service.subscribe(
            user_id=user_id,
            subscription=subscription,
            org_id=org_id,
            user_agent=user_agent,
            db=db,
        )

        if result.get("success"):
            return api_success(data={"id": result.get("id")})
        else:
            return api_error(
                ErrorCode.SYSTEM_INTERNAL_ERROR,
                result.get("error", "Failed to subscribe"),
            )
    except Exception as e:
        logger.error(f"Push subscribe error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/unsubscribe")
async def unsubscribe(
    body: PushUnsubscribeRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """取消推送订阅"""
    try:
        db = getattr(request.state, "db", None)
        success = await push_notification_service.unsubscribe(
            user_id=user_id,
            endpoint=body.endpoint,
            db=db,
        )

        if success:
            return api_success(data={"unsubscribed": True})
        else:
            return api_error(
                ErrorCode.SYSTEM_INTERNAL_ERROR,
                "Failed to unsubscribe",
            )
    except Exception as e:
        logger.error(f"Push unsubscribe error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
