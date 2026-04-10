"""Webhook management API endpoints."""

import logging

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.webhook_service import webhook_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


@router.post("/subscriptions")
async def create_subscription(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Register a new webhook subscription."""
    try:
        body = await req.json()
        url = body.get("url")
        events = body.get("events", ["*"])
        description = body.get("description", "")

        if not url:
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "url is required")

        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        sub = await webhook_service.register_subscription(
            org_id=org_id,
            url=url,
            events=events,
            description=description,
            db=getattr(req.state, "db", None),
        )
        return api_success(
            data={
                "subscription": sub.to_dict(),
                "secret": sub.secret,  # Only returned at creation
            }
        )
    except Exception as e:
        logger.error(f"Webhook subscription creation failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "Webhook操作失败")


@router.get("/subscriptions")
async def list_subscriptions(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """List all webhook subscriptions for the current org."""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
    subs = await webhook_service.list_subscriptions(
        org_id=org_id, db=getattr(req.state, "db", None)
    )
    return api_success(data={"subscriptions": subs})


@router.delete("/subscriptions/{sub_id}")
async def delete_subscription(
    sub_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Deactivate a webhook subscription."""
    success = await webhook_service.deactivate_subscription(
        sub_id, db=getattr(req.state, "db", None)
    )
    if not success:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "Subscription not found")
    return api_success(data={"deactivated": sub_id})


@router.get("/deliveries")
async def list_deliveries(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    limit: int = 50,
):
    """List recent webhook deliveries."""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
    deliveries = webhook_service.get_recent_deliveries(org_id=org_id, limit=limit)
    return api_success(data={"deliveries": deliveries})
