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
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "plan is required")

        try:
            plan = BillingPlan(plan_name)
        except ValueError:
            raise api_error(
                ErrorCode.VALIDATION_INVALID_INPUT, f"Invalid plan: {plan_name}"
            )

        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        sub = await billing_service.create_subscription(
            org_id, plan, db=getattr(req.state, "db", None)
        )
        return api_success(data={"subscription": sub.__dict__})
    except Exception as e:
        logger.error(f"Subscription failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "账单操作失败")


@router.post("/checkout")
async def create_checkout(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Create a Stripe Checkout Session and return the redirect URL."""
    try:
        body = await req.json()
        plan_id = body.get("plan_id")
        success_url = body.get("success_url", "")
        cancel_url = body.get("cancel_url", "")

        if not plan_id:
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "plan_id is required")

        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

        try:
            from app.services.payment_gateway import payment_gateway

            result = await payment_gateway.create_checkout_session(
                tenant_id=org_id,
                plan_id=plan_id,
                success_url=success_url,
                cancel_url=cancel_url,
            )
            return api_success(data=result)
        except ImportError:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "支付网关不可用")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Checkout creation failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "创建支付会话失败")


@router.post("/portal-session")
async def create_portal_session(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Create a Stripe Customer Portal session for subscription management."""
    try:
        body = await req.json()
        return_url = body.get("return_url", "")

        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

        from app.services.payment_gateway import payment_gateway

        result = await payment_gateway.create_portal_session(
            tenant_id=org_id, return_url=return_url
        )
        return api_success(data=result)
    except ImportError:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "支付网关不可用")
    except Exception as e:
        logger.error(f"Portal session creation failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "创建管理门户失败")


@router.get("/usage")
async def get_usage(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Get current org usage stats."""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

    db = getattr(req.state, "db", None)
    if not db:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

    try:
        # Read quotas
        quota_res = (
            await db.table("tenant_quotas")
            .select("*")
            .eq("org_id", org_id)
            .maybe_single()
            .execute()
        )
        quota = (quota_res.data if quota_res else None) or {}

        # Read credits
        credit_res = (
            await db.table("tenant_credits").select("*").eq("org_id", org_id).execute()
        )
        credits = (credit_res.data if credit_res else None) or []

        # Build usage stats
        monthly_token = next(
            (c for c in credits if c.get("credit_type") == "monthly_tokens"), {}
        )
        daily_token = next(
            (c for c in credits if c.get("credit_type") == "daily_tokens"), {}
        )

        return api_success(
            data={
                "monthly_tokens_used": monthly_token.get("used", 0),
                "monthly_token_limit": monthly_token.get("allocated", 0),
                "daily_tokens_used": daily_token.get("used", 0),
                "daily_token_limit": daily_token.get("allocated", 0),
                "storage_used_mb": quota.get("storage_used_mb", 0),
                "storage_limit_mb": quota.get("storage_limit_mb", 0),
            }
        )
    except Exception as e:
        logger.error(f"Usage stats failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取用量失败")


@router.post("/cancel")
async def cancel_subscription(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Cancel current subscription."""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
    success = await billing_service.cancel_subscription(
        org_id, db=getattr(req.state, "db", None)
    )
    return api_success(data={"cancelled": success})


@router.post("/webhook", deprecated=True)
async def billing_webhook(req: Request):
    """Handle billing provider webhooks (e.g., Stripe).

    DEPRECATED: Use POST /api/webhooks/stripe instead.
    This endpoint proxies to PaymentGateway.handle_webhook() for backwards compatibility.
    """
    from app.services.payment_gateway import payment_gateway

    logger.warning(
        "Deprecated billing webhook endpoint called — use /api/webhooks/stripe instead"
    )

    try:
        raw_body = await req.body()
        signature = req.headers.get("stripe-signature", "")

        if not signature:
            logger.warning("Billing webhook received without signature")
            raise api_error(
                ErrorCode.AUTH_PERMISSION_DENIED, "Missing webhook signature"
            )

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

    result = await billing_service.start_trial(
        org_id, days=days, db=getattr(req.state, "db", None)
    )
    return api_success(data=result)
