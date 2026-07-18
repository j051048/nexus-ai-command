from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from postgrest.exceptions import APIError

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
    rpc_query = MagicMock()
    rpc_query.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "change_id": "change-1",
                "org_id": "org-1",
                "status": "applied",
                "subscription": {
                    "plan": "professional",
                    "status": "active",
                    "access_source": "admin_override",
                },
            }
        )
    )
    client.rpc.return_value = rpc_query
    service._get_global_client = MagicMock(return_value=client)
    service._write_audit_log = AsyncMock()
    service._publish_entitlement_change = AsyncMock()
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
    client.rpc.assert_called_once()
    assert client.rpc.call_args.args[0] == "set_subscription_access_atomic"
    assert result["plan"] == "professional"
    assert result["status"] == "active"
    assert result["current_period_end"] == expires_at


@pytest.mark.asyncio
async def test_direct_membership_retry_reuses_database_change_id_and_event_once():
    service = SuperAdminService()
    client = MagicMock()
    first_query = MagicMock()
    first_query.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "change_id": "change-1",
                "org_id": "org-1",
                "subscription": {"plan": "professional", "status": "active"},
                "replayed": False,
            }
        )
    )
    replay_query = MagicMock()
    replay_query.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "change_id": "change-1",
                "org_id": "org-1",
                "subscription": {"plan": "professional", "status": "active"},
                "replayed": True,
            }
        )
    )
    client.rpc.side_effect = [first_query, replay_query]
    service._get_global_client = MagicMock(return_value=client)
    service._write_audit_log = AsyncMock()
    service._publish_entitlement_change = AsyncMock()
    service._invalidate_billing_cache = MagicMock()
    expires_at = (datetime.now(UTC) + timedelta(days=30)).isoformat()

    for _ in range(2):
        await service.admin_set_access(
            org_id="org-1",
            plan="professional",
            expires_at=expires_at,
            reason="Contract approved",
            admin_user_id="admin-1",
            idempotency_key="same-http-request",
        )

    first_params = client.rpc.call_args_list[0].args[1]
    replay_params = client.rpc.call_args_list[1].args[1]
    assert first_params["p_change_id"] == replay_params["p_change_id"]
    service._publish_entitlement_change.assert_awaited_once()


@pytest.mark.asyncio
async def test_change_plan_converges_on_atomic_access_writer():
    service = SuperAdminService()
    client = MagicMock()
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    client.table.return_value = query
    service._get_global_client = MagicMock(return_value=client)
    service._maybe_first = AsyncMock(
        return_value={"current_period_end": "2030-01-01T00:00:00+00:00"}
    )
    service.admin_set_access = AsyncMock(return_value={"plan": "enterprise"})

    await service.admin_change_plan(
        "org-1",
        "enterprise",
        "Annual upgrade",
        "admin-1",
        idempotency_key="change-plan-1",
    )

    service.admin_set_access.assert_awaited_once_with(
        org_id="org-1",
        plan="enterprise",
        expires_at="2030-01-01T00:00:00+00:00",
        reason="Annual upgrade",
        admin_user_id="admin-1",
        idempotency_key="change-plan-1",
        idempotency_scope="change-plan",
    )


@pytest.mark.asyncio
async def test_trial_management_converges_on_atomic_access_writer():
    service = SuperAdminService()
    service._get_global_client = MagicMock(return_value=MagicMock())
    service.admin_set_access = AsyncMock(
        return_value={"org_id": "org-1", "plan": "professional"}
    )

    result = await service.admin_manage_trial(
        "org-1",
        "start",
        14,
        "professional",
        "Pilot approved",
        "admin-1",
        idempotency_key="trial-1",
    )

    kwargs = service.admin_set_access.await_args.kwargs
    assert kwargs["status_override"] == "trialing"
    assert kwargs["idempotency_scope"] == "manage-trial"
    assert kwargs["idempotency_key"] == "trial-1"
    assert result["trial_days"] == 14


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


def test_super_admin_membership_writes_are_idempotency_protected():
    from app.core.idempotency_middleware import is_idempotency_protected_path

    assert is_idempotency_protected_path("/api/admin/organizations/org-1/access")
    assert is_idempotency_protected_path("/api/admin/organizations/org-1/access/adjust")
    assert is_idempotency_protected_path("/api/crm/customers")
    assert is_idempotency_protected_path("/api/approval/submit-smart")
    assert is_idempotency_protected_path("/api/inventory/out")


@pytest.mark.asyncio
async def test_subscription_request_decision_has_no_post_rpc_projection_writes():
    service = SuperAdminService()
    client = MagicMock()
    rpc_query = MagicMock()
    rpc_query.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "request_id": "request-1",
                "change_id": "change-1",
                "org_id": "org-1",
                "status": "approved",
                "plan": "enterprise",
                "current_period_end": "2030-01-01T00:00:00+00:00",
                "replayed": False,
            }
        )
    )
    client.rpc.return_value = rpc_query
    service._get_global_client = MagicMock(return_value=client)
    service._invalidate_billing_cache = MagicMock()
    service._publish_entitlement_change = AsyncMock()
    service._write_audit_log = AsyncMock()

    result = await service.decide_subscription_request(
        request_id="request-1",
        decision="approved",
        reason="Approved for production",
        admin_user_id="admin-1",
        plan="enterprise",
        expires_at="2030-01-01T00:00:00+00:00",
    )

    assert result["change_id"] == "change-1"
    client.table.assert_not_called()
    service._publish_entitlement_change.assert_awaited_once_with(
        "org-1", "change-1", "applied", "admin-1"
    )


@pytest.mark.asyncio
async def test_replayed_subscription_request_does_not_publish_duplicate_event():
    service = SuperAdminService()
    client = MagicMock()
    rpc_query = MagicMock()
    rpc_query.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "request_id": "request-1",
                "change_id": "change-1",
                "org_id": "org-1",
                "status": "approved",
                "plan": "enterprise",
                "current_period_end": "2030-01-01T00:00:00+00:00",
                "replayed": True,
            }
        )
    )
    client.rpc.return_value = rpc_query
    service._get_global_client = MagicMock(return_value=client)
    service._invalidate_billing_cache = MagicMock()
    service._publish_entitlement_change = AsyncMock()
    service._write_audit_log = AsyncMock()

    await service.decide_subscription_request(
        request_id="request-1",
        decision="approved",
        reason="Approved for production",
        admin_user_id="admin-1",
    )

    service._publish_entitlement_change.assert_not_awaited()


@pytest.mark.asyncio
async def test_atomic_membership_rpc_only_falls_back_when_migration_is_missing():
    service = SuperAdminService()
    client = MagicMock()
    rpc_query = MagicMock()
    rpc_query.execute = AsyncMock(
        side_effect=APIError(
            {
                "code": "PGRST202",
                "message": "function not found",
                "details": None,
                "hint": None,
            }
        )
    )
    client.rpc.return_value = rpc_query
    service._get_global_client = MagicMock(return_value=client)
    service._legacy_set_access = AsyncMock(
        return_value={
            "plan": "professional",
            "status": "active",
            "access_source": "admin_override",
        }
    )
    service._write_audit_log = AsyncMock()
    service._publish_entitlement_change = AsyncMock()

    result = await service.admin_set_access(
        org_id="org-1",
        plan="professional",
        expires_at=(datetime.now(UTC) + timedelta(days=30)).isoformat(),
        reason="Compatibility rollout",
        admin_user_id="admin-1",
    )

    service._legacy_set_access.assert_awaited_once()
    assert result["status"] == "active"


@pytest.mark.asyncio
async def test_atomic_membership_rpc_does_not_mask_integrity_failures():
    service = SuperAdminService()
    client = MagicMock()
    rpc_query = MagicMock()
    rpc_query.execute = AsyncMock(
        side_effect=APIError(
            {
                "code": "23505",
                "message": "duplicate key",
                "details": None,
                "hint": None,
            }
        )
    )
    client.rpc.return_value = rpc_query
    service._get_global_client = MagicMock(return_value=client)
    service._legacy_set_access = AsyncMock()

    with pytest.raises(APIError):
        await service.admin_set_access(
            org_id="org-1",
            plan="professional",
            expires_at=(datetime.now(UTC) + timedelta(days=30)).isoformat(),
            reason="Must fail closed",
            admin_user_id="admin-1",
        )

    service._legacy_set_access.assert_not_awaited()
