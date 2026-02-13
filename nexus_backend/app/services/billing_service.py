"""
Subscription billing service with plan management.

Provides plan catalog, subscription lifecycle, and Stripe integration stub.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class BillingPlan(Enum):
    """Available subscription plans."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


@dataclass
class PlanDetails:
    """Details of a subscription plan."""
    plan: BillingPlan
    name: str
    price_monthly_usd: float
    token_limit: int
    api_call_limit: int
    storage_mb: int
    features: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "plan": self.plan.value,
            "name": self.name,
            "price_monthly_usd": self.price_monthly_usd,
            "token_limit": self.token_limit,
            "api_call_limit": self.api_call_limit,
            "storage_mb": self.storage_mb,
            "features": self.features,
        }


PLAN_CATALOG: Dict[BillingPlan, PlanDetails] = {
    BillingPlan.FREE: PlanDetails(
        BillingPlan.FREE, "Free", 0, 50_000, 500, 100,
        ["basic_chat", "3_documents"],
    ),
    BillingPlan.STARTER: PlanDetails(
        BillingPlan.STARTER, "Starter", 29.0, 500_000, 5_000, 1_000,
        ["basic_chat", "documents", "tools", "email_support"],
    ),
    BillingPlan.PROFESSIONAL: PlanDetails(
        BillingPlan.PROFESSIONAL, "Professional", 99.0, 2_000_000, 20_000, 5_000,
        ["all_features", "priority_support", "api_access", "custom_tools"],
    ),
    BillingPlan.ENTERPRISE: PlanDetails(
        BillingPlan.ENTERPRISE, "Enterprise", 299.0, 10_000_000, 100_000, 50_000,
        ["all_features", "sla", "custom_integrations", "dedicated_support", "sso"],
    ),
}


@dataclass
class Subscription:
    """An organization's subscription."""
    org_id: str
    plan: BillingPlan
    status: str = "active"  # active, past_due, cancelled, trialing
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    current_period_end: Optional[str] = None


class BillingService:
    """Subscription and billing management."""

    def __init__(self):
        self._subscriptions: Dict[str, Subscription] = {}

    def get_plan_catalog(self) -> List[Dict]:
        """Get all available plans."""
        return [p.to_dict() for p in PLAN_CATALOG.values()]

    async def get_subscription(self, org_id: str, db=None) -> Subscription:
        """Get an org's current subscription."""
        if org_id in self._subscriptions:
            return self._subscriptions[org_id]

        # Check DB
        if db:
            try:
                res = await db.table("subscriptions").select("*").eq(
                    "org_id", org_id
                ).maybe_single().execute()
                if res.data:
                    sub = Subscription(
                        org_id=org_id,
                        plan=BillingPlan(res.data.get("plan", "free")),
                        status=res.data.get("status", "active"),
                        stripe_customer_id=res.data.get("stripe_customer_id"),
                        stripe_subscription_id=res.data.get("stripe_subscription_id"),
                        current_period_end=res.data.get("current_period_end"),
                    )
                    self._subscriptions[org_id] = sub
                    return sub
            except Exception as e:
                logger.debug(f"Subscription lookup failed: {e}")

        # Default to free plan
        sub = Subscription(org_id=org_id, plan=BillingPlan.FREE)
        self._subscriptions[org_id] = sub
        return sub

    async def create_subscription(
        self, org_id: str, plan: BillingPlan, db=None
    ) -> Subscription:
        """Create or update a subscription."""
        sub = Subscription(org_id=org_id, plan=plan, status="active")
        self._subscriptions[org_id] = sub

        if db:
            try:
                await db.table("subscriptions").upsert({
                    "org_id": org_id,
                    "plan": plan.value,
                    "status": "active",
                }).execute()
            except Exception as e:
                logger.warning(f"Failed to persist subscription: {e}")

        logger.info(f"Subscription created: {org_id} -> {plan.value}")
        return sub

    async def change_plan(
        self, org_id: str, new_plan: BillingPlan, db=None
    ) -> Subscription:
        """Change an org's plan."""
        return await self.create_subscription(org_id, new_plan, db)

    async def cancel_subscription(self, org_id: str, db=None) -> bool:
        """Cancel a subscription."""
        sub = self._subscriptions.get(org_id)
        if sub:
            sub.status = "cancelled"
            sub.plan = BillingPlan.FREE

        if db:
            try:
                await db.table("subscriptions").update({
                    "status": "cancelled",
                    "plan": "free",
                }).eq("org_id", org_id).execute()
            except Exception as e:
                logger.warning(f"Failed to cancel subscription in DB: {e}")

        return True

    async def handle_payment_webhook(self, event_type: str, data: Dict):
        """Handle payment provider webhook events."""
        logger.info(f"Billing webhook received: {event_type}")

        if event_type == "invoice.payment_succeeded":
            org_id = data.get("metadata", {}).get("org_id")
            if org_id and org_id in self._subscriptions:
                self._subscriptions[org_id].status = "active"

        elif event_type == "invoice.payment_failed":
            org_id = data.get("metadata", {}).get("org_id")
            if org_id and org_id in self._subscriptions:
                self._subscriptions[org_id].status = "past_due"

        elif event_type == "customer.subscription.deleted":
            org_id = data.get("metadata", {}).get("org_id")
            if org_id:
                await self.cancel_subscription(org_id)


# Global instance
billing_service = BillingService()
