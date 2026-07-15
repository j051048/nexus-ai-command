from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.billing_service import BillingPlan, Subscription
from app.services.super_admin_service import (
    SuperAdminService,
    canonical_subscription_map,
)


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


def test_unconfigured_organization_requires_membership_notice():
    subscription = Subscription(
        org_id="org-1",
        plan=BillingPlan.FREE,
        status="unconfigured",
        access_source="default",
    )

    payload = subscription.to_public_dict()

    assert payload["has_paid_access"] is False
    assert payload["notice_policy"] == "action_required"


def test_canonical_subscription_prefers_valid_membership_over_newer_expired_trial():
    now = datetime.now(UTC)
    subscriptions = [
        {
            "org_id": "org-1",
            "plan": "professional",
            "status": "active",
            "current_period_end": None,
            "approved_at": (now - timedelta(days=60)).isoformat(),
        },
        {
            "org_id": "org-1",
            "plan": "professional",
            "status": "trialing",
            "current_period_end": (now - timedelta(days=1)).isoformat(),
            "approved_at": now.isoformat(),
        },
    ]

    selected = canonical_subscription_map(subscriptions)["org-1"]

    assert selected["status"] == "active"
    assert selected["current_period_end"] is None


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
    assert query.upsert.call_args.kwargs["on_conflict"] == "org_id"
    assert result["plan"] == "professional"
    assert result["status"] == "active"
    assert result["current_period_end"] == expires_at


@pytest.mark.asyncio
async def test_admin_can_extend_membership_from_current_expiry():
    service = SuperAdminService()
    client = MagicMock()
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    client.table.return_value = query
    service._get_global_client = MagicMock(return_value=client)
    current_end = datetime.now(UTC) + timedelta(days=30)
    service._maybe_first = AsyncMock(
        return_value={
            "org_id": "org-1",
            "plan": "enterprise",
            "status": "active",
            "current_period_end": current_end.isoformat(),
        }
    )
    service.admin_set_access = AsyncMock(
        return_value={"org_id": "org-1", "plan": "enterprise", "status": "active"}
    )

    result = await service.admin_adjust_access_days(
        org_id="org-1",
        days=30,
        reason="Manual extension",
        admin_user_id="admin-1",
    )

    assert result["adjusted_days"] == 30
    args = service.admin_set_access.await_args.args
    extended_until = datetime.fromisoformat(args[2])
    assert timedelta(days=59) < extended_until - datetime.now(UTC) < timedelta(days=61)


@pytest.mark.asyncio
async def test_long_term_membership_cannot_be_accidentally_converted_by_adjustment():
    service = SuperAdminService()
    client = MagicMock()
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    client.table.return_value = query
    service._get_global_client = MagicMock(return_value=client)
    service._maybe_first = AsyncMock(
        return_value={
            "org_id": "org-1",
            "plan": "enterprise",
            "status": "active",
            "current_period_end": None,
        }
    )
    service.admin_set_access = AsyncMock()

    with pytest.raises(ValueError, match="长期有效会员无法增减天数"):
        await service.admin_adjust_access_days(
            org_id="org-1",
            days=30,
            reason="Manual extension",
            admin_user_id="admin-1",
        )

    service.admin_set_access.assert_not_awaited()
