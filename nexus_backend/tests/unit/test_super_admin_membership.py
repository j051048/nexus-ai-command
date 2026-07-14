from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.billing_service import BillingPlan, Subscription
from app.services.super_admin_service import SuperAdminService


def test_admin_approved_subscription_stays_quiet_until_expiry():
    subscription = Subscription(
        org_id="org-1",
        plan=BillingPlan.PROFESSIONAL,
        status="active",
        current_period_end=(datetime.now(UTC) + timedelta(days=30)).isoformat(),
        access_source="admin_approved",
    )

    payload = subscription.to_public_dict()

    assert payload["has_paid_access"] is True
    assert payload["notice_policy"] == "none"
    assert payload["status"] == "active"


def test_expired_subscription_requires_attention():
    subscription = Subscription(
        org_id="org-1",
        plan=BillingPlan.PROFESSIONAL,
        status="active",
        current_period_end=(datetime.now(UTC) - timedelta(days=1)).isoformat(),
        access_source="admin_approved",
    )

    payload = subscription.to_public_dict()

    assert payload["has_paid_access"] is False
    assert payload["notice_policy"] == "action_required"
    assert payload["status"] == "expired"


@pytest.mark.asyncio
async def test_admin_access_update_invalidates_billing_cache():
    service = SuperAdminService()
    client = MagicMock()
    query = MagicMock()
    query.eq.return_value = query
    query.upsert.return_value = query
    query.update.return_value = query
    query.insert.return_value = query
    query.execute = AsyncMock(return_value=SimpleNamespace(data=[{"org_id": "org-1"}]))
    client.table.return_value = query
    service._get_global_client = MagicMock(return_value=client)
    service._write_audit_log = AsyncMock()
    expires_at = (datetime.now(UTC) + timedelta(days=365)).isoformat()

    with patch.object(service, "_invalidate_billing_cache") as invalidate:
        result = await service.admin_set_access(
            org_id="org-1",
            plan="professional",
            expires_at=expires_at,
            reason="Contract approved",
            admin_user_id="admin-1",
        )

    invalidate.assert_called_once_with("org-1")
    assert result["plan"] == "professional"
    assert result["status"] == "active"
    assert result["current_period_end"] == expires_at
