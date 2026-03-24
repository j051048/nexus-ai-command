"""Subscription billing API endpoints."""

import logging

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.billing_service import BillingPlan, billing_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/billing", tags=["Billing"])


@router.get("/plans")
async def list_plans():
    """List all available subscription plans."""
    catalog = billing_service.get_plan_catalog()
    return api_success(data={"plans": catalog})


@router.get("/subscription")
async def get_subscription(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Get current org subscription."""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
    sub = await billing_service.get_subscription(org_id, db=getattr(req.state, "db", None))
    return api_success(data={"subscription": sub.__dict__ if sub else None})


@router.post("/subscribe")
async def subscribe(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Subscribe to a plan or change plan."""
    try:
        body = await req.json()
        plan_name = body.get("plan")
        if not plan_name:
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "plan is required")

        try:
            plan = BillingPlan(plan_name)
        except ValueError:
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, f"Invalid plan: {plan_name}")

        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        sub = await billing_service.create_subscription(org_id, plan, db=getattr(req.state, "db", None))
        return api_success(data={"subscription": sub.__dict__})
    except Exception as e:
        logger.error(f"Subscription failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "账单操作失败")


@router.post("/cancel")
async def cancel_subscription(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Cancel current subscription."""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
    success = await billing_service.cancel_subscription(org_id, db=getattr(req.state, "db", None))
    return api_success(data={"cancelled": success})


@router.post("/webhook", deprecated=True)
async def billing_webhook(req: Request):
    """Handle billing provider webhooks (e.g., Stripe).

    DEPRECATED: Use POST /api/webhooks/stripe instead.
    This endpoint proxies to PaymentGateway.handle_webhook() for backwards compatibility.
    """
    from app.services.payment_gateway import payment_gateway

    logger.warning("Deprecated billing webhook endpoint called — use /api/webhooks/stripe instead")

    try:
        raw_body = await req.body()
        signature = req.headers.get("stripe-signature", "")

        if not signature:
            logger.warning("Billing webhook received without signature")
            raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "Missing webhook signature")

        result = await payment_gateway.handle_webhook(raw_body, signature)
        return api_success(data=result)
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Billing webhook error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "账单操作失败")


@router.post("/trial")
async def start_trial(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Start a free trial for the organization."""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
    try:
        body = await req.json()
        days = body.get("days", 14)
    except Exception:
        days = 14

    result = await billing_service.start_trial(org_id, days=days, db=getattr(req.state, "db", None))
    return api_success(data=result)
