"""
Subscription billing service with plan management.

Provides plan catalog, subscription lifecycle, and Stripe integration.
In dev mode (no STRIPE_SECRET_KEY), billing is simulated locally.
In production, creates real Stripe Checkout Sessions and manages subscription lifecycle.
"""

import logging
import os
import time as _time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

# Detect dev mode when Stripe is not configured
_STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
_IS_DEV_MODE = not bool(_STRIPE_SECRET_KEY)

# Lazy-load stripe module only when key is present
_stripe = None


def _get_stripe():
    """Lazy-load and configure the stripe module."""
    global _stripe
    if _stripe is None and _STRIPE_SECRET_KEY:
        try:
            import stripe

            stripe.api_key = _STRIPE_SECRET_KEY
            _stripe = stripe
        except ImportError:
            logger.warning("stripe package not installed, falling back to dev mode")
    return _stripe


# Stripe Price IDs mapped by plan (read from settings — supports both legacy and canonical names)
def _get_stripe_price_ids() -> dict[str, str]:
    from app.core.config import settings

    return {
        "starter": settings.STRIPE_PRICE_STARTER,
        "professional": settings.STRIPE_PRICE_PROFESSIONAL,
        "enterprise": settings.STRIPE_PRICE_ENTERPRISE,
    }


class BillingPlan(Enum):
    """Available subscription plans."""

    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"

    @property
    def rate_tier(self) -> str:
        """Map billing plan to rate_limiting_service RateTier value."""
        return {
            "free": "free",
            "starter": "basic",
            "professional": "premium",
            "enterprise": "enterprise",
        }[self.value]


@dataclass
class PlanDetails:
    """Details of a subscription plan."""

    plan: BillingPlan
    name: str
    price_monthly_usd: float
    token_limit: int
    api_call_limit: int
    storage_mb: int
    features: list[str] = field(default_factory=list)
    human_readable_limits: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "plan": self.plan.value,
            "name": self.name,
            "price_monthly_usd": self.price_monthly_usd,
            "token_limit": self.token_limit,
            "api_call_limit": self.api_call_limit,
            "storage_mb": self.storage_mb,
            "features": self.features,
            "human_readable_limits": self.human_readable_limits,
        }


PLAN_CATALOG: dict[BillingPlan, PlanDetails] = {
    BillingPlan.FREE: PlanDetails(
        BillingPlan.FREE,
        "Free",
        0,
        50_000,
        500,
        100,
        ["basic_chat", "3_documents"],
        {
            "conversations": "约 20 次 AI 对话/月",
            "reports": "约 3 份报告/月",
            "storage": "100 MB 存储",
        },
    ),
    BillingPlan.STARTER: PlanDetails(
        BillingPlan.STARTER,
        "Starter",
        29.0,
        500_000,
        5_000,
        1_000,
        ["basic_chat", "documents", "tools", "email_support"],
        {
            "conversations": "约 200 次 AI 对话/月",
            "reports": "约 50 份报告/月",
            "storage": "1 GB 存储",
        },
    ),
    BillingPlan.PROFESSIONAL: PlanDetails(
        BillingPlan.PROFESSIONAL,
        "Professional",
        99.0,
        2_000_000,
        20_000,
        5_000,
        ["all_features", "priority_support", "api_access", "custom_tools"],
        {
            "conversations": "约 800 次 AI 对话/月",
            "reports": "约 200 份报告/月",
            "storage": "5 GB 存储",
        },
    ),
    BillingPlan.ENTERPRISE: PlanDetails(
        BillingPlan.ENTERPRISE,
        "Enterprise",
        299.0,
        10_000_000,
        100_000,
        50_000,
        ["all_features", "sla", "custom_integrations", "dedicated_support", "sso"],
        {
            "conversations": "约 4000 次 AI 对话/月",
            "reports": "不限报告",
            "storage": "50 GB 存储",
        },
    ),
}


@dataclass
class Subscription:
    """An organization's subscription."""

    org_id: str
    plan: BillingPlan
    status: str = "active"  # active, past_due, cancelled, trialing
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    current_period_end: str | None = None


class BillingService:
    """Subscription and billing management."""

    def __init__(self):
        # P0 Fix: Memory cache is only used as a short-lived cache layer.
        # Always read-through from DB on cache miss. TTL-based invalidation.
        self._subscriptions: dict[str, tuple[Subscription, float]] = (
            {}
        )  # org_id -> (sub, cached_at_timestamp)
        self._CACHE_TTL = 60.0  # seconds — refetch from DB after TTL

    def get_plan_catalog(self) -> list[dict]:
        """Get all available plans."""
        plans = [p.to_dict() for p in PLAN_CATALOG.values()]
        if _IS_DEV_MODE:
            for p in plans:
                p["mode"] = "sandbox"
                p["_dev_warning"] = "Stripe not configured. Billing is simulated."
        return plans

    async def get_subscription(self, org_id: str, db=None) -> Subscription:
        """Get an org's current subscription. Always checks DB if cache expired."""
        # Check memory cache with TTL
        if org_id in self._subscriptions:
            cached_sub, cached_at = self._subscriptions[org_id]
            if (_time.time() - cached_at) < self._CACHE_TTL:
                return cached_sub

        # Always try DB first (source of truth)
        if db:
            try:
                res = (
                    await db.table("subscriptions")
                    .select("*")
                    .eq("org_id", org_id)
                    .maybe_single()
                    .execute()
                )
                if res.data:
                    sub = Subscription(
                        org_id=org_id,
                        plan=BillingPlan(res.data.get("plan", "free")),
                        status=res.data.get("status", "active"),
                        stripe_customer_id=res.data.get("stripe_customer_id"),
                        stripe_subscription_id=res.data.get("stripe_subscription_id"),
                        current_period_end=res.data.get("current_period_end"),
                    )
                    self._subscriptions[org_id] = (sub, _time.time())
                    return sub
            except Exception as e:
                # maybe_single() returns 204 when no row exists — not a real error
                err_str = str(e)
                if "204" not in err_str:
                    logger.error(f"Subscription lookup failed: {e}")

        # Default to free plan
        sub = Subscription(org_id=org_id, plan=BillingPlan.FREE)
        self._subscriptions[org_id] = (sub, _time.time())
        return sub

    async def create_subscription(
        self, org_id: str, plan: BillingPlan, db=None
    ) -> Subscription | dict:
        """Create or update a subscription.

        In production (Stripe configured): creates a Checkout Session URL.
        In dev mode: immediately activates the subscription locally.
        """
        # Production: create Stripe Checkout Session
        stripe = _get_stripe()
        price_id = _get_stripe_price_ids().get(plan.value, "")
        if stripe and price_id and plan != BillingPlan.FREE:
            try:
                # Find or create Stripe customer
                customer_id = await self._get_or_create_stripe_customer(org_id, db)

                session = stripe.checkout.Session.create(
                    customer=customer_id,
                    mode="subscription",
                    line_items=[{"price": price_id, "quantity": 1}],
                    success_url=os.getenv(
                        "STRIPE_SUCCESS_URL",
                        "https://app.example.com/payments?status=success",
                    ),
                    cancel_url=os.getenv(
                        "STRIPE_CANCEL_URL",
                        "https://app.example.com/payments?status=cancelled",
                    ),
                    metadata={"org_id": org_id, "plan": plan.value},
                    subscription_data={
                        "metadata": {"org_id": org_id, "plan": plan.value}
                    },
                )
                logger.info(
                    f"Stripe Checkout Session created: {session.id} for org={org_id} plan={plan.value}"
                )
                return {
                    "checkout_url": session.url,
                    "session_id": session.id,
                    "plan": plan.value,
                    "status": "pending_payment",
                }
            except Exception as e:
                logger.error(f"Stripe Checkout Session creation failed: {e}")
                # Fall through to local subscription as fallback

        # Dev mode or free plan: immediate local activation
        sub = Subscription(org_id=org_id, plan=plan, status="active")
        self._subscriptions[org_id] = (sub, _time.time())

        if db:
            try:
                await (
                    db.table("subscriptions")
                    .upsert(
                        {
                            "org_id": org_id,
                            "plan": plan.value,
                            "status": "active",
                        }
                    )
                    .execute()
                )
            except Exception as e:
                logger.warning(f"Failed to persist subscription: {e}")

        logger.info(f"Subscription created (local): {org_id} -> {plan.value}")

        # Sync billing plan to rate limiting tier
        self._sync_tier_to_rate_limiter(org_id, plan)

        return sub

    @staticmethod
    def _sync_tier_to_rate_limiter(org_id: str, plan: BillingPlan):
        """Sync billing plan change to rate_limiting_service tier cache.

        Invalidates the cached tier so next rate-limit check picks up the new plan.
        """
        try:
            from app.services.rate_limiting_service import rate_limiting_service

            # Invalidate all cached users for this org so they re-resolve on next request
            stale_keys = [uid for uid, _ in rate_limiting_service._tier_cache.items()]
            for uid in stale_keys:
                rate_limiting_service.invalidate_cache(uid)
            logger.info(
                f"Rate limiter cache invalidated for org {org_id} (plan={plan.value}, tier={plan.rate_tier})"
            )
        except Exception as e:
            logger.error(f"Rate limiter tier sync failed (non-critical): {e}")

    async def _get_or_create_stripe_customer(self, org_id: str, db=None) -> str:
        """Get existing Stripe customer ID or create a new one."""
        # Check DB for existing customer ID
        if db:
            try:
                res = (
                    await db.table("subscriptions")
                    .select("stripe_customer_id")
                    .eq("org_id", org_id)
                    .maybe_single()
                    .execute()
                )
                if res.data and res.data.get("stripe_customer_id"):
                    return res.data["stripe_customer_id"]
            except Exception:
                pass

        # Check memory cache
        if org_id in self._subscriptions:
            cached_sub, _ = self._subscriptions[org_id]
            if cached_sub.stripe_customer_id:
                return cached_sub.stripe_customer_id

        # Create new Stripe customer
        stripe = _get_stripe()
        customer = stripe.Customer.create(metadata={"org_id": org_id})
        customer_id = customer.id

        # Persist customer ID
        if db:
            try:
                await db.table("subscriptions").upsert(
                    {"org_id": org_id, "stripe_customer_id": customer_id}
                ).execute()
            except Exception as e:
                logger.warning(f"Failed to persist Stripe customer ID: {e}")

        return customer_id

    async def change_plan(
        self, org_id: str, new_plan: BillingPlan, db=None
    ) -> Subscription:
        """Change an org's plan."""
        return await self.create_subscription(org_id, new_plan, db)

    async def cancel_subscription(self, org_id: str, db=None) -> bool:
        """Cancel a subscription at period end (not immediately)."""
        if org_id in self._subscriptions:
            sub, _ = self._subscriptions[org_id]
            # P2 Fix: Don't immediately downgrade — mark for cancellation at period end
            sub.status = "cancel_at_period_end"

        if db:
            try:
                await (
                    db.table("subscriptions")
                    .update(
                        {
                            "status": "cancel_at_period_end",
                        }
                    )
                    .eq("org_id", org_id)
                    .execute()
                )
            except Exception as e:
                logger.warning(f"Failed to cancel subscription in DB: {e}")

        logger.info(f"Subscription marked for cancellation at period end: {org_id}")
        return True

    async def handle_payment_webhook(
        self, event_type: str, data: dict, signature: str = None
    ):
        """Handle payment provider webhook events.

        P1 Security Fix: Validates Stripe webhook signature when configured.
        """
        # P1 Security: Verify Stripe webhook signature
        if _STRIPE_SECRET_KEY and signature:
            webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
            if webhook_secret:
                try:
                    import stripe

                    stripe.Webhook.construct_event(
                        data.get("_raw_body", "{}"), signature, webhook_secret
                    )
                except Exception as e:
                    logger.warning(f"Stripe webhook signature verification failed: {e}")
                    return  # Reject unverified webhooks
            else:
                logger.warning(
                    "STRIPE_WEBHOOK_SECRET not configured, skipping signature verification"
                )

        logger.info(f"Billing webhook received: {event_type}")

        if event_type == "invoice.payment_succeeded":
            org_id = data.get("metadata", {}).get("org_id")
            if org_id and org_id in self._subscriptions:
                sub, _ = self._subscriptions[org_id]
                sub.status = "active"

        elif event_type == "invoice.payment_failed":
            org_id = data.get("metadata", {}).get("org_id")
            if org_id and org_id in self._subscriptions:
                sub, _ = self._subscriptions[org_id]
                sub.status = "past_due"

        elif event_type == "customer.subscription.deleted":
            org_id = data.get("metadata", {}).get("org_id")
            if org_id:
                await self.cancel_subscription(org_id)

    async def start_trial(
        self,
        org_id: str,
        days: int = 14,
        plan: BillingPlan = BillingPlan.PROFESSIONAL,
        db=None,
    ) -> dict:
        """Start a free trial for an organization.

        P1 Enhancement: Allows new orgs to try paid features before committing.
        """
        trial_end = datetime.now(UTC) + timedelta(days=days)
        sub = Subscription(
            org_id=org_id,
            plan=plan,
            status="trialing",
            current_period_end=trial_end.isoformat(),
        )
        self._subscriptions[org_id] = (sub, _time.time())

        if db:
            try:
                await (
                    db.table("subscriptions")
                    .upsert(
                        {
                            "org_id": org_id,
                            "plan": plan.value,
                            "status": "trialing",
                            "current_period_end": trial_end.isoformat(),
                        }
                    )
                    .execute()
                )
            except Exception as e:
                logger.warning(f"Failed to persist trial subscription: {e}")

        logger.info(
            f"Trial started: org={org_id} plan={plan.value} ends={trial_end.isoformat()}"
        )
        return {
            "org_id": org_id,
            "plan": plan.value,
            "status": "trialing",
            "trial_ends": trial_end.isoformat(),
            "days": days,
            "mode": "sandbox" if _IS_DEV_MODE else "production",
        }

    async def check_expired_trials(self, db=None):
        """P2 Fix: Check and downgrade expired trials."""
        now = datetime.now(UTC)
        expired = [
            org_id
            for org_id, (sub, _ts) in self._subscriptions.items()
            if sub.status == "trialing"
            and sub.current_period_end
            and datetime.fromisoformat(sub.current_period_end) < now
        ]
        for org_id in expired:
            sub, _ = self._subscriptions[org_id]
            sub.plan = BillingPlan.FREE
            sub.status = "active"
            sub.current_period_end = None
            logger.info(f"Trial expired, downgraded to FREE: {org_id}")

            if db:
                try:
                    await (
                        db.table("subscriptions")
                        .update(
                            {
                                "plan": "free",
                                "status": "active",
                                "current_period_end": None,
                            }
                        )
                        .eq("org_id", org_id)
                        .execute()
                    )
                except Exception as e:
                    logger.warning(f"Failed to persist trial expiry for {org_id}: {e}")

        # Also check cancel_at_period_end subscriptions
        cancelled = [
            org_id
            for org_id, (sub, _ts) in self._subscriptions.items()
            if sub.status == "cancel_at_period_end"
            and sub.current_period_end
            and datetime.fromisoformat(sub.current_period_end) < now
        ]
        for org_id in cancelled:
            sub, _ = self._subscriptions[org_id]
            sub.plan = BillingPlan.FREE
            sub.status = "cancelled"
            logger.info(f"Subscription period ended, downgraded to FREE: {org_id}")

            if db:
                try:
                    await (
                        db.table("subscriptions")
                        .update(
                            {
                                "plan": "free",
                                "status": "cancelled",
                            }
                        )
                        .eq("org_id", org_id)
                        .execute()
                    )
                except Exception as e:
                    logger.warning(f"Failed to persist cancellation for {org_id}: {e}")


# Global instance
billing_service = BillingService()
