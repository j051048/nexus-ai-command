"""Subscription billing API endpoints."""

import hashlib
import hmac
import logging
import os

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.billing_service import BillingPlan, billing_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/billing", tags=["Billing"])

_STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


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
            return api_error(ErrorCode.VALIDATION_INVALID_INPUT, "plan is required")

        try:
            plan = BillingPlan(plan_name)
        except ValueError:
            return api_error(ErrorCode.VALIDATION_INVALID_INPUT, f"Invalid plan: {plan_name}")

        org_id = getattr(req.state, "org_id", None) or "default"
        sub = await billing_service.create_subscription(org_id, plan, db=getattr(req.state, "db", None))
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
    success = await billing_service.cancel_subscription(org_id, db=getattr(req.state, "db", None))
    return api_success(data={"cancelled": success})


@router.post("/webhook")
async def billing_webhook(req: Request):
    """Handle billing provider webhooks (e.g., Stripe)."""
    try:
        raw_body = await req.body()

        # P2 Security: Verify webhook signature in production
        if _STRIPE_WEBHOOK_SECRET:
            sig_header = req.headers.get("stripe-signature", "")
            if not sig_header:
                logger.warning("Billing webhook received without signature")
                return api_error(ErrorCode.AUTH_PERMISSION_DENIED, "Missing webhook signature")

            # Verify HMAC signature
            timestamp, _, sig = "", "", ""
            for part in sig_header.split(","):
                k, _, v = part.strip().partition("=")
                if k == "t":
                    timestamp = v
                elif k == "v1":
                    sig = v

            signed_payload = f"{timestamp}.{raw_body.decode()}"
            expected = hmac.new(_STRIPE_WEBHOOK_SECRET.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, sig):
                logger.warning("Billing webhook signature verification failed")
                return api_error(ErrorCode.AUTH_PERMISSION_DENIED, "Invalid webhook signature")
        else:
            logger.warning("STRIPE_WEBHOOK_SECRET not set — webhook signature verification skipped (dev mode)")

        import json

        body = json.loads(raw_body)
        event_type = body.get("type", "")
        data = body.get("data", {})
        await billing_service.handle_payment_webhook(event_type, data)
        return api_success(data={"received": True})
    except Exception as e:
        logger.error(f"Billing webhook error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/trial")
async def start_trial(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Start a free trial for the organization."""
    org_id = getattr(req.state, "org_id", None) or "default"
    try:
        body = await req.json()
        days = body.get("days", 14)
    except Exception:
        days = 14

    result = await billing_service.start_trial(org_id, days=days, db=getattr(req.state, "db", None))
    return api_success(data=result)
