from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.super_admin_governance_service import SuperAdminGovernanceService


def _client_with_assignment(assignment):
    client = MagicMock()
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    query.execute = AsyncMock(
        return_value=SimpleNamespace(data=[assignment] if assignment else [])
    )
    client.table.return_value = query
    return client


@pytest.mark.asyncio
async def test_unassigned_super_admin_keeps_owner_compatibility():
    service = SuperAdminGovernanceService()
    service._client = MagicMock(return_value=_client_with_assignment(None))

    context = await service.get_admin_context("admin-1")

    assert context["admin_role"] == "platform_owner"
    assert context["permissions"] == ["*"]


@pytest.mark.asyncio
async def test_scoped_operator_cannot_use_owner_permission():
    service = SuperAdminGovernanceService()
    service._client = MagicMock(
        return_value=_client_with_assignment(
            {
                "user_id": "operator-1",
                "admin_role": "billing_operator",
                "permissions": [],
                "active": True,
            }
        )
    )

    with pytest.raises(PermissionError):
        await service.assert_permission("operator-1", "manage_admins")

    await service.assert_permission("operator-1", "manage_memberships")


@pytest.mark.asyncio
async def test_event_failure_does_not_break_persisted_schedule(monkeypatch):
    captured: dict = {}
    versions = MagicMock()
    versions.insert.side_effect = lambda payload: captured.update(payload) or versions
    versions.execute = AsyncMock(
        side_effect=lambda: SimpleNamespace(data=[dict(captured)])
    )

    audit = MagicMock()
    audit.insert.return_value = audit
    audit.execute = AsyncMock(return_value=SimpleNamespace(data=[]))

    client = MagicMock()
    client.table.side_effect = lambda name: (
        versions if name == "subscription_access_versions" else audit
    )

    service = SuperAdminGovernanceService()
    service._client = MagicMock(return_value=client)
    publish = AsyncMock(side_effect=RuntimeError("event bus unavailable"))
    monkeypatch.setattr(
        "app.services.super_admin_governance_service.event_bus.publish", publish
    )

    result = await service.schedule_access_change(
        org_id="org-1",
        plan="professional",
        expires_at="2030-12-31T00:00:00+00:00",
        effective_at="2030-01-01T00:00:00+00:00",
        reason="年度合同",
        admin_user_id="admin-1",
    )

    assert result["org_id"] == "org-1"
    assert result["change_status"] == "scheduled"
    assert publish.await_count == 1
