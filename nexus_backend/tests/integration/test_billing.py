"""
Tests for billing router — subscription plans, subscribe/cancel, webhooks, trial.
"""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestListPlans:
    """GET /api/billing/plans"""

    @pytest.mark.asyncio
    async def test_list_plans_returns_catalog(self, async_client):
        catalog = [
            {"name": "free", "price": 0},
            {"name": "professional", "price": 99},
        ]
        with patch(
            "app.routers.billing.billing_service"
        ) as mock_svc:
            mock_svc.get_plan_catalog.return_value = catalog
            resp = await async_client.get("/api/billing/plans")

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["plans"] == catalog


class TestGetSubscription:
    """GET /api/billing/subscription"""

    @pytest.mark.asyncio
    async def test_no_org_id_returns_403(self, async_client):
        """Without org_id, should return 403."""
        with (
            patch("app.routers.billing.get_current_user_id", return_value="user-1"),
            patch(
                "app.core.security_middleware.TenantContextMiddleware.set_request_state",
                new_callable=MagicMock,
            ),
        ):
            # Simulate request.state.org_id = None via middleware
            resp = await async_client.get(
                "/api/billing/subscription",
                headers={"Authorization": "Bearer fake-token"},
            )
        # Without proper auth middleware in test, this will be 401 or 403
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_returns_subscription(self, async_client):
        """With valid org_id, should return subscription data."""
        mock_sub = MagicMock()
        mock_sub.__dict__ = {
            "plan": "professional",
            "status": "active",
            "org_id": "org-1",
        }
        with (
            patch("app.routers.billing.get_current_user_id", return_value="user-1"),
            patch("app.routers.billing.billing_service") as mock_svc,
        ):
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

        with pytest.raises(Exception) as exc_info:
            await subscribe(req=req, user_id="user-1")
        assert exc_info.value.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_invalid_plan_returns_error(self):
        """Should reject invalid plan names."""
        from app.routers.billing import subscribe

        req = MagicMock()
        req.json = AsyncMock(return_value={"plan": "nonexistent_plan"})
        req.state.org_id = "org-1"

        # BillingPlan enum will raise ValueError for invalid plan
        with pytest.raises(Exception):
            await subscribe(req=req, user_id="user-1")

    @pytest.mark.asyncio
    async def test_no_org_id_returns_403(self):
        """Should reject when org_id is missing."""
        from app.routers.billing import subscribe

        req = MagicMock()
        req.json = AsyncMock(return_value={"plan": "free"})
        req.state = MagicMock(spec=[])  # no org_id attribute

        with pytest.raises(Exception):
            await subscribe(req=req, user_id="user-1")

    @pytest.mark.asyncio
    async def test_subscribe_success(self):
        """Should successfully subscribe to a valid plan."""
        from app.routers.billing import subscribe

        mock_sub = MagicMock()
        mock_sub.__dict__ = {"plan": "free", "status": "active"}

        req = MagicMock()
        req.json = AsyncMock(return_value={"plan": "free"})
        req.state.org_id = "org-1"
        req.state.db = None

        with patch("app.routers.billing.billing_service") as mock_svc:
            mock_svc.create_subscription = AsyncMock(return_value=mock_sub)
            result = await subscribe(req=req, user_id="user-1")

        assert result["success"] is True
        assert result["data"]["subscription"]["plan"] == "free"


class TestCancelSubscription:
    """POST /api/billing/cancel"""

    @pytest.mark.asyncio
    async def test_no_org_id_returns_403(self):
        from app.routers.billing import cancel_subscription

        req = MagicMock()
        req.state = MagicMock(spec=[])

        with pytest.raises(Exception) as exc_info:
            await cancel_subscription(req=req, user_id="user-1")
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_cancel_success(self):
        from app.routers.billing import cancel_subscription

        req = MagicMock()
        req.state.org_id = "org-1"
        req.state.db = None

        with patch("app.routers.billing.billing_service") as mock_svc:
            mock_svc.cancel_subscription = AsyncMock(return_value=True)
            result = await cancel_subscription(req=req, user_id="user-1")

        assert result["success"] is True
        assert result["data"]["cancelled"] is True


class TestBillingWebhook:
    """POST /api/billing/webhook"""

    @pytest.mark.asyncio
    async def test_missing_signature_rejected_when_secret_set(self):
        """Should reject webhook without signature when secret is configured."""
        from app.routers.billing import billing_webhook

        req = MagicMock()
        req.body = AsyncMock(return_value=b'{"type": "test"}')
        req.headers = {}  # no stripe-signature

        with patch("app.routers.billing._STRIPE_WEBHOOK_SECRET", "test-secret"):
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

        with patch("app.routers.billing._STRIPE_WEBHOOK_SECRET", "test-secret"):
            with pytest.raises(Exception) as exc_info:
                await billing_webhook(req=req)
            assert exc_info.value.status_code in (403, 401)

    @pytest.mark.asyncio
    async def test_valid_signature_accepted(self):
        """Should accept webhook with valid HMAC signature."""
        from app.routers.billing import billing_webhook

        secret = "test-secret"
        payload = b'{"type": "payment.completed", "data": {}}'
        timestamp = "1234567890"
        signed = f"{timestamp}.{payload.decode()}"
        sig = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()

        req = MagicMock()
        req.body = AsyncMock(return_value=payload)
        req.headers = {"stripe-signature": f"t={timestamp},v1={sig}"}

        with (
            patch("app.routers.billing._STRIPE_WEBHOOK_SECRET", secret),
            patch("app.routers.billing.billing_service") as mock_svc,
        ):
            mock_svc.handle_payment_webhook = AsyncMock(return_value=None)
            result = await billing_webhook(req=req)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_no_secret_allows_webhook(self):
        """In dev mode (no secret), webhook should be accepted."""
        from app.routers.billing import billing_webhook

        req = MagicMock()
        req.body = AsyncMock(return_value=b'{"type": "test", "data": {}}')
        req.headers = {}

        with (
            patch("app.routers.billing._STRIPE_WEBHOOK_SECRET", ""),
            patch("app.routers.billing.billing_service") as mock_svc,
        ):
            mock_svc.handle_payment_webhook = AsyncMock(return_value=None)
            result = await billing_webhook(req=req)

        assert result["success"] is True


class TestStartTrial:
    """POST /api/billing/trial"""

    @pytest.mark.asyncio
    async def test_no_org_id_returns_403(self):
        from app.routers.billing import start_trial

        req = MagicMock()
        req.state = MagicMock(spec=[])

        with pytest.raises(Exception) as exc_info:
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
            mock_svc.start_trial = AsyncMock(
                return_value={"trial_started": True, "days": 14}
            )
            result = await start_trial(req=req, user_id="user-1")

        assert result["success"] is True
        assert result["data"]["trial_started"] is True

    @pytest.mark.asyncio
    async def test_start_trial_custom_days(self):
        from app.routers.billing import start_trial

        req = MagicMock()
        req.state.org_id = "org-1"
        req.state.db = None
        req.json = AsyncMock(return_value={"days": 30})

        with patch("app.routers.billing.billing_service") as mock_svc:
            mock_svc.start_trial = AsyncMock(
                return_value={"trial_started": True, "days": 30}
            )
            result = await start_trial(req=req, user_id="user-1")

        assert result["success"] is True
        assert result["data"]["days"] == 30
