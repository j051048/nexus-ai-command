from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.routers.super_admin import (
    AdjustAccessDaysRequest,
    SetAccessRequest,
    SubscriptionDecisionRequest,
    admin_adjust_access_days,
    admin_set_access,
    decide_subscription_request,
    list_subscription_requests,
)


@pytest.mark.asyncio
async def test_admin_set_access_route_returns_canonical_membership():
    expires_at = datetime.now(UTC) + timedelta(days=365)
    expected = {
        "org_id": "org-1",
        "plan": "professional",
        "status": "active",
        "current_period_end": expires_at.isoformat(),
    }
    with patch("app.routers.super_admin.super_admin_service") as service:
        service.admin_set_access = AsyncMock(return_value=expected)
        result = await admin_set_access(
            org_id="org-1",
            body=SetAccessRequest(
                plan="professional",
                expires_at=expires_at,
                reason="Contract approved",
            ),
            user_id="admin-1",
        )

    assert result["success"] is True
    assert result["data"] == expected
    service.admin_set_access.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_adjust_access_days_route():
    expected = {
        "org_id": "org-1",
        "plan": "enterprise",
        "status": "active",
        "adjusted_days": 30,
    }
    with patch("app.routers.super_admin.super_admin_service") as service:
        service.admin_adjust_access_days = AsyncMock(return_value=expected)
        result = await admin_adjust_access_days(
            org_id="org-1",
            body=AdjustAccessDaysRequest(days=30),
            user_id="admin-1",
        )

    assert result["success"] is True
    assert result["data"] == expected
    service.admin_adjust_access_days.assert_awaited_once_with(
        org_id="org-1",
        days=30,
        reason="平台管理员手动调整会员期限",
        admin_user_id="admin-1",
    )


@pytest.mark.asyncio
async def test_admin_can_list_pending_membership_requests():
    requests = [{"id": "request-1", "status": "pending", "org_id": "org-1"}]
    with patch("app.routers.super_admin.super_admin_service") as service:
        service.list_subscription_requests = AsyncMock(return_value=requests)
        result = await list_subscription_requests(
            status="pending", limit=100, user_id="admin-1"
        )

    assert result["data"]["requests"] == requests


@pytest.mark.asyncio
async def test_approval_decision_contract_supports_exact_expiry():
    expires_at = datetime.now(UTC) + timedelta(days=90)
    with patch("app.routers.super_admin.super_admin_service") as service:
        service.decide_subscription_request = AsyncMock(
            return_value={"request_id": "request-1", "status": "approved"}
        )
        result = await decide_subscription_request(
            request_id="request-1",
            body=SubscriptionDecisionRequest(
                decision="approved",
                reason="Approved for production use",
                plan="enterprise",
                expires_at=expires_at,
            ),
            user_id="admin-1",
        )

    assert result["success"] is True
    kwargs = service.decide_subscription_request.await_args.kwargs
    assert kwargs["plan"] == "enterprise"
    assert kwargs["expires_at"] == expires_at.isoformat()
