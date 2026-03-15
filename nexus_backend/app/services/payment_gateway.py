"""
Stripe Payment Gateway Service.

Provides Stripe Checkout, Subscription lifecycle, Usage-based billing,
and Webhook processing. Gracefully degrades when Stripe is not configured.

Requires: pip install stripe
"""

import logging
import time
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-load stripe SDK
# ---------------------------------------------------------------------------
_stripe_mod = None


def _get_stripe():
    """Lazy-load and configure the stripe module using Settings."""
    global _stripe_mod
    if _stripe_mod is not None:
        return _stripe_mod
    try:
        from app.core.config import settings
        if not settings.STRIPE_SECRET_KEY:
            return None
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        _stripe_mod = stripe
        return stripe
    except ImportError:
        logger.warning("stripe package not installed. Run: pip install stripe")
        return None


# ---------------------------------------------------------------------------
# Plan ↔ Stripe Price mapping
# ---------------------------------------------------------------------------
_PLAN_PRICE_MAP: dict[str, str] | None = None


def _get_plan_price_map() -> dict[str, str]:
    global _PLAN_PRICE_MAP
    if _PLAN_PRICE_MAP is None:
        from app.core.config import settings
        _PLAN_PRICE_MAP = {
            "basic": settings.STRIPE_PRICE_BASIC,
            "premium": settings.STRIPE_PRICE_PREMIUM,
            "enterprise": settings.STRIPE_PRICE_ENTERPRISE,
        }
    return _PLAN_PRICE_MAP


# Map Stripe Price ID back to internal tier name
def _price_to_tier(price_id: str) -> str | None:
    for tier, pid in _get_plan_price_map().items():
        if pid and pid == price_id:
            return tier
    return None


# ---------------------------------------------------------------------------
# PaymentGatewayService
# ---------------------------------------------------------------------------
class PaymentGatewayService:
    """Stripe payment integration with graceful fallback."""

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def _require_stripe():
        s = _get_stripe()
        if s is None:
            raise RuntimeError(
                "Stripe is not configured. Set STRIPE_SECRET_KEY in environment variables. "
                "Also ensure the stripe package is installed: pip install stripe"
            )
        return s

    @staticmethod
    def _get_db():
        from app.core.database import supabase
        return supabase

    # -- Checkout ------------------------------------------------------------
    async def create_checkout_session(
        self,
        tenant_id: str,
        plan_id: str,
        success_url: str,
        cancel_url: str,
    ) -> dict[str, Any]:
        """Create a Stripe Checkout Session for a subscription plan.

        Returns {"url": str, "session_id": str}.
        """
        stripe = self._require_stripe()

        price_map = _get_plan_price_map()
        price_id = price_map.get(plan_id)
        if not price_id:
            raise ValueError(
                f"Unknown plan '{plan_id}'. Available plans: {list(price_map.keys())}"
            )

        # Get or create Stripe customer for this tenant
        customer_id = await self._ensure_stripe_customer(tenant_id)

        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"tenant_id": tenant_id, "plan_id": plan_id},
            client_reference_id=tenant_id,
        )
        return {"url": session.url, "session_id": session.id}

    # -- Subscription CRUD ---------------------------------------------------
    async def create_subscription(
        self, tenant_id: str, stripe_price_id: str
    ) -> dict[str, Any]:
        """Create a subscription directly (bypassing Checkout)."""
        stripe = self._require_stripe()
        customer_id = await self._ensure_stripe_customer(tenant_id)

        sub = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": stripe_price_id}],
            metadata={"tenant_id": tenant_id},
        )
        # Persist subscription mapping
        await self._save_subscription_record(tenant_id, sub)
        return {
            "subscription_id": sub.id,
            "status": sub.status,
            "current_period_end": sub.current_period_end,
        }

    async def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Cancel a subscription at period end."""
        stripe = self._require_stripe()
        sub = stripe.Subscription.modify(
            subscription_id, cancel_at_period_end=True
        )
        return {
            "subscription_id": sub.id,
            "status": sub.status,
            "cancel_at_period_end": sub.cancel_at_period_end,
        }

    async def get_subscription_status(self, tenant_id: str) -> dict[str, Any] | None:
        """Return current subscription info for a tenant from DB."""
        db = self._get_db()
        if db is None:
            return None
        try:
            resp = await (
                db.table("tenant_subscriptions")
                .select("*")
                .eq("tenant_id", tenant_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = resp.data if resp else []
            return rows[0] if rows else None
        except Exception as exc:
            logger.warning("get_subscription_status failed: %s", exc)
            return None

    # -- Usage-based billing -------------------------------------------------
    async def create_usage_record(
        self,
        subscription_item_id: str,
        quantity: int,
        timestamp: int | None = None,
    ) -> dict[str, Any]:
        """Report metered usage to Stripe for usage-based billing."""
        stripe = self._require_stripe()
        ts = timestamp or int(time.time())
        record = stripe.SubscriptionItem.create_usage_record(
            subscription_item_id,
            quantity=quantity,
            timestamp=ts,
            action="increment",
        )
        return {"id": record.id, "quantity": record.quantity, "timestamp": record.timestamp}

    # -- Webhook processing --------------------------------------------------
    async def handle_webhook(self, payload: bytes, signature: str) -> dict[str, Any]:
        """Verify Stripe signature and dispatch to event handlers.

        Returns {"event_type": str, "handled": bool}.
        """
        stripe = self._require_stripe()
        from app.core.config import settings

        if not settings.STRIPE_WEBHOOK_SECRET:
            raise RuntimeError("STRIPE_WEBHOOK_SECRET is not configured")

        event = stripe.Webhook.construct_event(
            payload, signature, settings.STRIPE_WEBHOOK_SECRET
        )
        event_type: str = event["type"]
        data_obj = event["data"]["object"]

        handler = self._EVENT_HANDLERS.get(event_type)
        if handler:
            await handler(self, data_obj, event)
            logger.info("Stripe webhook handled: %s (id=%s)", event_type, event.get("id"))
            return {"event_type": event_type, "handled": True}
        else:
            logger.debug("Stripe webhook ignored: %s", event_type)
            return {"event_type": event_type, "handled": False}

    # -- Event handler methods -----------------------------------------------
    async def _on_checkout_completed(self, session: dict, event: dict):
        """Handle checkout.session.completed — activate subscription."""
        tenant_id = session.get("client_reference_id") or session.get("metadata", {}).get("tenant_id")
        subscription_id = session.get("subscription")
        if not tenant_id or not subscription_id:
            logger.warning("checkout.session.completed missing tenant_id or subscription_id")
            return
        # Fetch full subscription to determine tier
        stripe = _get_stripe()
        if stripe:
            sub = stripe.Subscription.retrieve(subscription_id)
            await self._save_subscription_record(tenant_id, sub)
            # Determine tier from price
            if sub.get("items", {}).get("data"):
                price_id = sub["items"]["data"][0].get("price", {}).get("id", "")
                tier = _price_to_tier(price_id)
                if tier:
                    await self._update_tenant_tier(tenant_id, tier)

    async def _on_invoice_paid(self, invoice: dict, event: dict):
        """Handle invoice.paid — confirm payment."""
        tenant_id = invoice.get("metadata", {}).get("tenant_id")
        sub_id = invoice.get("subscription")
        logger.info("Invoice paid: tenant=%s subscription=%s", tenant_id, sub_id)

    async def _on_invoice_payment_failed(self, invoice: dict, event: dict):
        """Handle invoice.payment_failed — flag tenant."""
        tenant_id = invoice.get("metadata", {}).get("tenant_id")
        logger.warning("Invoice payment failed: tenant=%s", tenant_id)
        if tenant_id:
            db = self._get_db()
            if db:
                try:
                    await (
                        db.table("tenants")
                        .update({"payment_status": "past_due"})
                        .eq("id", tenant_id)
                        .execute()
                    )
                except Exception as exc:
                    logger.error("Failed to flag tenant past_due: %s", exc)

    async def _on_subscription_updated(self, sub: dict, event: dict):
        """Handle customer.subscription.updated — sync tier."""
        tenant_id = sub.get("metadata", {}).get("tenant_id")
        if not tenant_id:
            return
        await self._save_subscription_record(tenant_id, sub)
        if sub.get("items", {}).get("data"):
            price_id = sub["items"]["data"][0].get("price", {}).get("id", "")
            tier = _price_to_tier(price_id)
            if tier:
                await self._update_tenant_tier(tenant_id, tier)

    async def _on_subscription_deleted(self, sub: dict, event: dict):
        """Handle customer.subscription.deleted — downgrade to free."""
        tenant_id = sub.get("metadata", {}).get("tenant_id")
        if tenant_id:
            await self._update_tenant_tier(tenant_id, "free")
            logger.info("Subscription deleted, tenant %s downgraded to free", tenant_id)

    # Dispatch table
    _EVENT_HANDLERS = {
        "checkout.session.completed": _on_checkout_completed,
        "invoice.paid": _on_invoice_paid,
        "invoice.payment_failed": _on_invoice_payment_failed,
        "customer.subscription.updated": _on_subscription_updated,
        "customer.subscription.deleted": _on_subscription_deleted,
    }

    # -- Internal helpers ----------------------------------------------------
    async def _ensure_stripe_customer(self, tenant_id: str) -> str:
        """Get existing Stripe customer ID or create one for the tenant."""
        db = self._get_db()
        if db:
            try:
                resp = await (
                    db.table("tenants")
                    .select("stripe_customer_id, name")
                    .eq("id", tenant_id)
                    .limit(1)
                    .execute()
                )
                rows = resp.data if resp else []
                if rows and rows[0].get("stripe_customer_id"):
                    return rows[0]["stripe_customer_id"]
                tenant_name = rows[0].get("name", "") if rows else ""
            except Exception:
                tenant_name = ""
        else:
            tenant_name = ""

        # Create new Stripe customer
        stripe = _get_stripe()
        customer = stripe.Customer.create(
            metadata={"tenant_id": tenant_id},
            name=tenant_name or f"Tenant {tenant_id}",
        )
        # Persist mapping
        if db:
            try:
                await (
                    db.table("tenants")
                    .update({"stripe_customer_id": customer.id})
                    .eq("id", tenant_id)
                    .execute()
                )
            except Exception as exc:
                logger.warning("Failed to save stripe_customer_id: %s", exc)

        return customer.id

    async def _save_subscription_record(self, tenant_id: str, sub) -> None:
        """Upsert subscription info into tenant_subscriptions table."""
        db = self._get_db()
        if not db:
            return
        # sub can be a Stripe Subscription object or dict
        sub_dict = dict(sub) if not isinstance(sub, dict) else sub
        record = {
            "tenant_id": tenant_id,
            "stripe_subscription_id": sub_dict.get("id", ""),
            "status": sub_dict.get("status", ""),
            "current_period_start": datetime.fromtimestamp(
                sub_dict.get("current_period_start", 0), tz=UTC
            ).isoformat() if sub_dict.get("current_period_start") else None,
            "current_period_end": datetime.fromtimestamp(
                sub_dict.get("current_period_end", 0), tz=UTC
            ).isoformat() if sub_dict.get("current_period_end") else None,
            "cancel_at_period_end": sub_dict.get("cancel_at_period_end", False),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        try:
            await (
                db.table("tenant_subscriptions")
                .upsert(record, on_conflict="tenant_id,stripe_subscription_id")
                .execute()
            )
        except Exception as exc:
            logger.warning("Failed to save subscription record: %s", exc)

    async def _update_tenant_tier(self, tenant_id: str, tier: str) -> None:
        """Update the tenant's tier/plan in the tenants table."""
        db = self._get_db()
        if not db:
            return
        try:
            await (
                db.table("tenants")
                .update({"tier": tier, "updated_at": datetime.now(UTC).isoformat()})
                .eq("id", tenant_id)
                .execute()
            )
            logger.info("Tenant %s tier updated to '%s'", tenant_id, tier)
        except Exception as exc:
            logger.warning("Failed to update tenant tier: %s", exc)


# Singleton
payment_gateway = PaymentGatewayService()
