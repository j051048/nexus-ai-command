"""
Webhook subscription and delivery service.

Provides event-driven webhook delivery to external consumers with:
- Subscription management (register, list, deactivate)
- HMAC signature verification
- Delivery with exponential backoff retry
- Event bus integration for automatic forwarding
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class WebhookEvent(Enum):
    """Events that can trigger webhook delivery."""
    APPROVAL_SUBMITTED = "approval.submitted"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_REJECTED = "approval.rejected"
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_UPDATED = "document.updated"
    DEAL_WON = "deal.won"
    DEAL_LOST = "deal.lost"
    USER_CREATED = "user.created"
    CHAT_COMPLETED = "chat.completed"
    SYSTEM_ALERT = "system.alert"


@dataclass
class WebhookSubscription:
    """A registered webhook subscription."""
    id: str
    org_id: str
    url: str
    events: list[str]
    secret: str
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    failure_count: int = 0
    max_failures: int = 10
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "org_id": self.org_id,
            "url": self.url,
            "events": self.events,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "failure_count": self.failure_count,
            "description": self.description,
        }


@dataclass
class WebhookDelivery:
    """Record of a webhook delivery attempt."""
    id: str
    subscription_id: str
    event: str
    payload: dict[str, Any]
    status: str = "pending"  # pending, success, failed
    attempts: int = 0
    max_attempts: int = 3
    response_code: int | None = None
    response_body: str | None = None
    next_retry_at: float | None = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subscription_id": self.subscription_id,
            "event": self.event,
            "status": self.status,
            "attempts": self.attempts,
            "response_code": self.response_code,
            "created_at": self.created_at,
        }


class WebhookService:
    """Webhook subscription management and delivery."""

    def __init__(self):
        self._subscriptions: dict[str, WebhookSubscription] = {}
        self._deliveries: list[WebhookDelivery] = []
        self._max_deliveries = 10000

    def sign_payload(self, payload: str, secret: str) -> str:
        """Create HMAC-SHA256 signature for a payload with timestamp (replay-attack resistant)."""
        ts = str(int(time.time()))
        signed_content = f"{ts}.{payload}"
        sig = hmac.new(
            secret.encode("utf-8"),
            signed_content.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"t={ts},v1={sig}"

    def verify_signature(
        self, payload: str, signature: str, secret: str, tolerance: int = 300
    ) -> bool:
        """Verify an incoming webhook signature with timestamp validation.

        P0 Fix: Validates that the timestamp is within ±tolerance seconds to
        prevent replay attacks.
        """
        try:
            parts = dict(p.split("=", 1) for p in signature.split(","))
            ts = parts.get("t")
            v1 = parts.get("v1")
            if not ts or not v1:
                return False
            # Timestamp tolerance check (default ±5 minutes)
            if abs(time.time() - int(ts)) > tolerance:
                logger.warning("Webhook signature rejected: timestamp out of tolerance")
                return False
            signed_content = f"{ts}.{payload}"
            expected = hmac.new(
                secret.encode("utf-8"),
                signed_content.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, v1)
        except Exception as e:
            logger.warning(f"Webhook signature verification error: {e}")
            return False

    async def register_subscription(
        self,
        org_id: str,
        url: str,
        events: list[str],
        secret: str = None,
        description: str = "",
        db=None,
    ) -> WebhookSubscription:
        """Register a new webhook subscription."""
        sub_id = str(uuid.uuid4())[:12]
        if not secret:
            secret = f"whsec_{uuid.uuid4().hex[:24]}"

        sub = WebhookSubscription(
            id=sub_id,
            org_id=org_id,
            url=url,
            events=events,
            secret=secret,
            description=description,
        )
        self._subscriptions[sub_id] = sub

        # Persist to DB
        if db:
            try:
                await db.table("webhook_subscriptions").insert(
                    {
                        "id": sub_id,
                        "org_id": org_id,
                        "url": url,
                        "events": events,
                        "secret_hash": hashlib.sha256(secret.encode()).hexdigest(),
                        "is_active": True,
                        "description": description,
                    }
                ).execute()
            except Exception as e:
                logger.warning(f"Failed to persist webhook subscription: {e}")

        logger.info(f"Webhook subscription registered: {sub_id} for {url}")
        return sub

    async def list_subscriptions(self, org_id: str, db=None) -> list[dict]:
        """List all subscriptions for an org."""
        results = [
            sub.to_dict()
            for sub in self._subscriptions.values()
            if sub.org_id == org_id and sub.is_active
        ]
        return results

    async def deactivate_subscription(self, sub_id: str, db=None) -> bool:
        """Deactivate a webhook subscription."""
        sub = self._subscriptions.get(sub_id)
        if not sub:
            return False
        sub.is_active = False

        if db:
            try:
                await db.table("webhook_subscriptions").update(
                    {"is_active": False}
                ).eq("id", sub_id).execute()
            except Exception as e:
                logger.warning(f"Failed to deactivate webhook in DB: {e}")

        return True

    async def deliver(self, event: str, payload: dict, org_id: str):
        """Find matching subscriptions and queue deliveries."""
        matching = [
            sub
            for sub in self._subscriptions.values()
            if sub.is_active
            and sub.org_id == org_id
            and (event in sub.events or "*" in sub.events)
        ]

        for sub in matching:
            delivery = WebhookDelivery(
                id=str(uuid.uuid4())[:12],
                subscription_id=sub.id,
                event=event,
                payload=payload,
            )
            self._deliveries.append(delivery)
            asyncio.create_task(self._send_webhook(delivery, sub))

        # Trim delivery history
        if len(self._deliveries) > self._max_deliveries:
            self._deliveries = self._deliveries[-5000:]

    async def _send_webhook(
        self, delivery: WebhookDelivery, subscription: WebhookSubscription
    ) -> bool:
        """Send a webhook with retry and exponential backoff."""
        payload_json = json.dumps(
            {
                "event": delivery.event,
                "payload": delivery.payload,
                "delivery_id": delivery.id,
                "timestamp": datetime.utcnow().isoformat(),
            },
            ensure_ascii=False,
        )
        signature = self.sign_payload(payload_json, subscription.secret)
        # Extract timestamp from signed header for the HTTP header
        sig_parts = dict(p.split("=", 1) for p in signature.split(","))

        for attempt in range(delivery.max_attempts):
            delivery.attempts = attempt + 1
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        subscription.url,
                        content=payload_json,
                        headers={
                            "Content-Type": "application/json",
                            "X-Webhook-Signature": signature,
                            "X-Webhook-Timestamp": sig_parts.get("t", ""),
                            "X-Webhook-Event": delivery.event,
                            "X-Webhook-Delivery-Id": delivery.id,
                        },
                    )
                    delivery.response_code = resp.status_code
                    delivery.response_body = resp.text[:500]

                    if 200 <= resp.status_code < 300:
                        delivery.status = "success"
                        subscription.failure_count = 0
                        return True

            except Exception as e:
                delivery.response_body = str(e)[:500]
                logger.warning(
                    f"Webhook delivery {delivery.id} attempt {attempt + 1} failed: {e}"
                )

            # Exponential backoff before retry
            if attempt < delivery.max_attempts - 1:
                backoff = min(2 ** attempt * 5, 60)
                await asyncio.sleep(backoff)

        # All attempts failed
        delivery.status = "failed"
        subscription.failure_count += 1

        if subscription.failure_count >= subscription.max_failures:
            subscription.is_active = False
            logger.warning(
                f"Webhook subscription {subscription.id} deactivated after "
                f"{subscription.max_failures} consecutive failures"
            )

        return False

    def get_recent_deliveries(
        self, org_id: str = None, limit: int = 50
    ) -> list[dict]:
        """Get recent webhook deliveries."""
        deliveries = self._deliveries
        if org_id:
            sub_ids = {
                s.id
                for s in self._subscriptions.values()
                if s.org_id == org_id
            }
            deliveries = [d for d in deliveries if d.subscription_id in sub_ids]

        return [d.to_dict() for d in deliveries[-limit:]]


# Global instance
webhook_service = WebhookService()
