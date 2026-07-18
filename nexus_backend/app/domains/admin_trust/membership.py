"""Pure membership rules shared by platform administration services.

This module has no database or HTTP dependencies. Keeping entitlement state
classification here makes the rule independently testable and gives the
admin-trust domain a stable handover boundary.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

VALID_PLANS = frozenset({"free", "starter", "professional", "enterprise"})
INACTIVE_STATUSES = frozenset({"past_due", "suspended", "cancelled"})


def parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO timestamp and normalize naive values to UTC."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def access_state(
    subscription: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> str:
    """Classify the effective entitlement state of one subscription row."""
    if not subscription:
        return "unconfigured"
    reference_time = now or datetime.now(UTC)
    expires_at = parse_datetime(subscription.get("current_period_end"))
    if expires_at and expires_at <= reference_time:
        return "expired"
    status = subscription.get("status")
    if status in INACTIVE_STATUSES:
        return str(status)
    if subscription.get("plan") == "free":
        return "free"
    return "active"
