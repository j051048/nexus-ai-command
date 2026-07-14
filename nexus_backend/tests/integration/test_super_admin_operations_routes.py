from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.routers.super_admin import (
    AccessChangeActionRequest,
    BatchSubscriptionDecisionRequest,
    CommercialRecordRequest,
    PlatformAdminAssignmentRequest,
    ScheduleAccessRequest,
    batch_decide_subscription_requests,
    get_operational_analytics,
    get_organization_360,
    list_operational_exceptions,
    rollback_access_change,
    schedule_access_change,
    set_admin_assignment,
    upsert_commercial_record,
)


@pytest.mark.asyncio
async def test_schedule_access_change_supports_future_effective_time():
    effective_at = datetime.now(UTC) + timedelta(days=7)
    expires_at = effective_at + timedelta(days=365)
    with patch("app.routers.super_admin.super_admin_governance_service") as service:
        service.schedule_access_change = AsyncMock(
            return_value={"id": "change-1", "change_status": "scheduled"}
        )
        result = await schedule_access_change(
            org_id="org-1",
            body=ScheduleAccessRequest(
                plan="enterprise",
                expires_at=expires_at,
                effective_at=effective_at,
                reason="Contract starts next week",
            ),
            user_id="admin-1",
        )

    assert result["data"]["change_status"] == "scheduled"
    kwargs = service.schedule_access_change.await_args.kwargs
    assert kwargs["effective_at"] == effective_at.isoformat()


@pytest.mark.asyncio
async def test_access_change_can_be_rolled_back():
    with patch("app.routers.super_admin.super_admin_governance_service") as service:
        service.rollback_access_change = AsyncMock(
            return_value={"rolled_back_change_id": "change-1"}
        )
        result = await rollback_access_change(
            change_id="change-1",
            body=AccessChangeActionRequest(reason="Incorrect expiry date"),
            user_id="admin-1",
        )

    assert result["success"] is True
    service.rollback_access_change.assert_awaited_once()


@pytest.mark.asyncio
async def test_commercial_record_keeps_payment_evidence_separate():
    body = CommercialRecordRequest(
        org_id="org-1",
        order_number="ORDER-2026-001",
        contract_number="CONTRACT-1",
        amount_cents=1200000,
        payment_status="paid",
    )
    with patch("app.routers.super_admin.super_admin_governance_service") as service:
        service.upsert_commercial_record = AsyncMock(return_value=body.model_dump())
        result = await upsert_commercial_record(body=body, user_id="finance-1")

    assert result["data"]["amount_cents"] == 1200000
    assert result["data"]["payment_status"] == "paid"


@pytest.mark.asyncio
async def test_batch_decision_reports_partial_failures():
    with patch("app.routers.super_admin.super_admin_service") as service:
        service.decide_subscription_request = AsyncMock(
            side_effect=[{"request_id": "request-1"}, ValueError("already reviewed")]
        )
        result = await batch_decide_subscription_requests(
            body=BatchSubscriptionDecisionRequest(
                request_ids=["request-1", "request-2"],
                decision="approved",
                reason="Annual contract approved",
            ),
            user_id="admin-1",
        )

    assert len(result["data"]["completed"]) == 1
    assert result["data"]["failed"][0]["request_id"] == "request-2"


@pytest.mark.asyncio
async def test_organization_360_and_exception_contracts():
    with patch("app.routers.super_admin.super_admin_insights_service") as service:
        service.get_organization_360 = AsyncMock(
            return_value={"id": "org-1", "usage_30d": {"cost_usd": 1.2}}
        )
        service.list_operational_exceptions = AsyncMock(
            return_value=[{"id": "expiring:org-1", "severity": "high"}]
        )
        service.get_operational_analytics = AsyncMock(
            return_value={"average_review_hours": 2.5}
        )
        overview = await get_organization_360(org_id="org-1", user_id="admin-1")
        exceptions = await list_operational_exceptions(user_id="admin-1")
        analytics = await get_operational_analytics(user_id="admin-1")

    assert overview["data"]["usage_30d"]["cost_usd"] == 1.2
    assert exceptions["data"]["exceptions"][0]["severity"] == "high"
    assert analytics["data"]["average_review_hours"] == 2.5


@pytest.mark.asyncio
async def test_platform_owner_can_assign_scoped_admin_role():
    body = PlatformAdminAssignmentRequest(
        user_id="operator-1",
        admin_role="billing_operator",
        permissions=[],
        active=True,
    )
    with patch("app.routers.super_admin.super_admin_governance_service") as service:
        service.set_admin_assignment = AsyncMock(return_value=body.model_dump())
        result = await set_admin_assignment(
            target_user_id="operator-1", body=body, user_id="owner-1"
        )

    assert result["data"]["admin_role"] == "billing_operator"
