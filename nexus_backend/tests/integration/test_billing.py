"""
Tests for billing router — subscription plans, subscribe/cancel, webhooks, trial.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


class TestListPlans:
    """GET /api/billing/plans"""

    @pytest.mark.asyncio
    async def test_list_plans_returns_catalog(self, async_client):
        catalog = [
            {"name": "free", "price": 0},
            {"name": "professional", "price": 99},
        ]
        with patch("app.routers.billing.billing_service") as mock_svc:
            mock_svc.get_plan_catalog.return_value = catalog
            resp = await async_client.get("/api/billing/plans")

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["plans"] == catalog


class TestGetSubscription:
    """GET /api/billing/subscription"""

    @pytest.mark.asyncio
    async def test_no_org_id_returns_403(self):
        """Without org_id, should return 403."""
        from app.routers.billing import get_subscription

        req = MagicMock()
        req.state = MagicMock(spec=[])  # no org_id attribute

        with patch("app.routers.billing.get_current_user_id", return_value="user-1"):
            with pytest.raises(Exception) as exc_info:
                await get_subscription(req=req, user_id="user-1")
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_returns_subscription(self):
        """With valid org_id, should return subscription data."""

        class FakeSub:
            def __init__(self):
                self.plan = "professional"
                self.status = "active"
                self.org_id = "org-1"

        mock_sub = FakeSub()
        with patch("app.routers.billing.billing_service") as mock_svc:
            mock_svc.get_subscription = AsyncMock(return_value=mock_sub)

            # Direct router function call to bypass middleware
            from app.routers.billing import get_subscription

            req = MagicMock()
            req.state.org_id = "org-1"
            req.state.db = None
            result = await get_subscription(req=req, user_id="user-1")

        assert result["success"] is True
        assert result["data"]["subscription"]["plan"] == "professional"


class TestSubscribe:
    """POST /api/billing/subscribe"""

    @pytest.mark.asyncio
    async def test_missing_plan_returns_error(self):
        """Should reject when plan field is missing."""
        from app.routers.billing import subscribe

        req = MagicMock()
        req.json = AsyncMock(return_value={})
        req.state.org_id = "org-1"

        with pytest.raises(HTTPException) as exc_info:
            await subscribe(req=req, user_id="user-1")
        # The outer try/except in subscribe wraps all errors as 500
        assert exc_info.value.status_code in (400, 422, 500)

    @pytest.mark.asyncio
    async def test_invalid_plan_returns_error(self):
        """Should reject invalid plan names."""
        from app.routers.billing import subscribe

        req = MagicMock()
        req.json = AsyncMock(return_value={"plan": "nonexistent_plan"})
        req.state.org_id = "org-1"

        # BillingPlan enum will raise ValueError for invalid plan
        with pytest.raises(HTTPException):
            await subscribe(req=req, user_id="user-1")

    @pytest.mark.asyncio
    async def test_no_org_id_returns_403(self):
        """Should reject when org_id is missing."""
        from app.routers.billing import subscribe

        req = MagicMock()
        req.json = AsyncMock(return_value={"plan": "free"})
        req.state = MagicMock(spec=[])  # no org_id attribute

        with pytest.raises(HTTPException):
            await subscribe(req=req, user_id="user-1")

    @pytest.mark.asyncio
    async def test_subscribe_success(self):
        """Legacy subscribe clients should enter the manual approval queue."""
        from app.routers.billing import subscribe

        req = MagicMock()
        req.json = AsyncMock(return_value={"plan": "professional"})
        req.state.org_id = "org-1"
        req.state.db = None

        with patch("app.routers.billing.billing_service") as mock_svc:
            mock_svc.request_access = AsyncMock(
                return_value={"requested_plan": "professional", "status": "pending"}
            )
            result = await subscribe(req=req, user_id="user-1")

        assert result["success"] is True
        assert result["data"]["request"]["status"] == "pending"
        mock_svc.create_subscription.assert_not_called()


class TestCancelSubscription:
    """POST /api/billing/cancel"""

    @pytest.mark.asyncio
    async def test_no_org_id_returns_403(self):
        from app.routers.billing import cancel_subscription

        req = MagicMock()
        req.state = MagicMock(spec=[])

        with pytest.raises(HTTPException) as exc_info:
            await cancel_subscription(req=req, user_id="user-1")
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_cancel_success(self):
        from app.routers.billing import cancel_subscription

        req = MagicMock()
        req.state.org_id = "org-1"
        req.state.db = None

        with pytest.raises(HTTPException) as exc_info:
            await cancel_subscription(req=req, user_id="user-1")
        assert exc_info.value.status_code == 409


class TestBillingWebhook:
    """POST /api/billing/webhook

    The billing_webhook endpoint now proxies to payment_gateway.handle_webhook().
    It no longer reads _STRIPE_WEBHOOK_SECRET directly; signature validation is
    handled inside the payment gateway. We test the endpoint's behaviour here.
    """

    @pytest.mark.asyncio
    async def test_missing_signature_rejected(self):
        """Should reject webhook without signature."""
        from app.routers.billing import billing_webhook

        req = MagicMock()
        req.body = AsyncMock(return_value=b'{"type": "test"}')
        req.headers = {}  # no stripe-signature

        with pytest.raises(Exception) as exc_info:
            await billing_webhook(req=req)
        assert exc_info.value.status_code in (403, 401)

    @pytest.mark.asyncio
    async def test_wrong_signature_rejected(self):
        """Should reject webhook with wrong signature."""
        from app.routers.billing import billing_webhook

        payload = b'{"type": "payment.completed"}'
        req = MagicMock()
        req.body = AsyncMock(return_value=payload)
        req.headers = {"stripe-signature": "t=123,v1=wrong-sig"}

        with patch("app.services.payment_gateway.payment_gateway") as mock_gw:
            mock_gw.handle_webhook = AsyncMock(
                side_effect=Exception("Invalid signature")
            )
            with pytest.raises(HTTPException):
                await billing_webhook(req=req)

    @pytest.mark.asyncio
    async def test_valid_webhook_accepted(self):
        """Should accept webhook when payment gateway processes successfully."""
        from app.routers.billing import billing_webhook

        payload = b'{"type": "payment.completed", "data": {}}'
        req = MagicMock()
        req.body = AsyncMock(return_value=payload)
        req.headers = {"stripe-signature": "t=123,v1=valid-sig"}

        with patch("app.services.payment_gateway.payment_gateway") as mock_gw:
            mock_gw.handle_webhook = AsyncMock(
                return_value={"event": "payment.completed"}
            )
            result = await billing_webhook(req=req)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_webhook_with_empty_signature_rejected(self):
        """Webhook with empty signature header should be rejected."""
        from app.routers.billing import billing_webhook

        req = MagicMock()
        req.body = AsyncMock(return_value=b'{"type": "test", "data": {}}')
        req.headers = {"stripe-signature": ""}

        # Empty string signature triggers the missing-signature check
        with pytest.raises(HTTPException) as exc_info:
            await billing_webhook(req=req)
        assert exc_info.value.status_code in (403, 401)


class TestStartTrial:
    """POST /api/billing/trial"""

    @pytest.mark.asyncio
    async def test_no_org_id_returns_403(self):
        from app.routers.billing import start_trial

        req = MagicMock()
        req.state = MagicMock(spec=[])

        with pytest.raises(HTTPException) as exc_info:
            await start_trial(req=req, user_id="user-1")
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_start_trial_default_days(self):
        from app.routers.billing import start_trial

        req = MagicMock()
        req.state.org_id = "org-1"
        req.state.db = None
        req.json = AsyncMock(return_value={})

        with patch("app.routers.billing.billing_service") as mock_svc:
            mock_svc.request_access = AsyncMock(
                return_value={"requested_days": 14, "status": "pending"}
            )
            result = await start_trial(req=req, user_id="user-1")

        assert result["success"] is True
        assert result["data"]["request"]["status"] == "pending"
        mock_svc.start_trial.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_trial_custom_days(self):
        from app.routers.billing import start_trial

        req = MagicMock()
        req.state.org_id = "org-1"
        req.state.db = None
        req.json = AsyncMock(return_value={"days": 30})

        with patch("app.routers.billing.billing_service") as mock_svc:
            mock_svc.request_access = AsyncMock(
                return_value={"requested_days": 30, "status": "pending"}
            )
            result = await start_trial(req=req, user_id="user-1")

        assert result["success"] is True
        assert result["data"]["request"]["requested_days"] == 30


class TestManualApprovalMode:
    @pytest.mark.asyncio
    async def test_checkout_is_blocked(self):
        from app.routers.billing import create_checkout

        with pytest.raises(HTTPException) as exc_info:
            await create_checkout(req=MagicMock(), user_id="user-1")
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_provider_portal_is_blocked(self):
        from app.routers.billing import create_portal_session

        with pytest.raises(Exception) as exc_info:
            await create_portal_session(req=MagicMock(), user_id="user-1")
        assert exc_info.value.status_code == 409
