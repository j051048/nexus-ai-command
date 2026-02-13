"""Subscription billing API endpoints."""

import logging
from fastapi import APIRouter, Request, Depends
from app.core.auth import get_current_user_id
from app.core.errors import api_success, api_error, ErrorCode
from app.services.billing_service import billing_service, BillingPlan

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
    org_id = getattr(req.state, "org_id", None) or "default"
    sub = await billing_service.get_subscription(
        org_id, db=getattr(req.state, "db", None)
    )
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
            return api_error(ErrorCode.VALIDATION_ERROR, "plan is required")

        try:
            plan = BillingPlan(plan_name)
        except ValueError:
            return api_error(ErrorCode.VALIDATION_ERROR, f"Invalid plan: {plan_name}")

        org_id = getattr(req.state, "org_id", None) or "default"
        sub = await billing_service.create_subscription(
            org_id, plan, db=getattr(req.state, "db", None)
        )
        return api_success(data={"subscription": sub.__dict__})
    except Exception as e:
        logger.error(f"Subscription failed: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/cancel")
async def cancel_subscription(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Cancel current subscription."""
    org_id = getattr(req.state, "org_id", None) or "default"
    success = await billing_service.cancel_subscription(
        org_id, db=getattr(req.state, "db", None)
    )
    return api_success(data={"cancelled": success})


@router.post("/webhook")
async def billing_webhook(req: Request):
    """Handle billing provider webhooks (e.g., Stripe)."""
    try:
        body = await req.json()
        event_type = body.get("type", "")
        data = body.get("data", {})
        await billing_service.handle_payment_webhook(event_type, data)
        return api_success(data={"received": True})
    except Exception as e:
        logger.error(f"Billing webhook error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
