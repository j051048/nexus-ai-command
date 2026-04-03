"""
PaymentGatewayService 单元测试
覆盖: Checkout Session, Subscription CRUD, Webhook 处理, Usage Record
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.payment_gateway import PaymentGatewayService


class TestRequireStripe:
    """Stripe 可用性检查"""

    def test_stripe_not_configured_raises(self):
        with patch("app.services.payment_gateway._get_stripe", return_value=None):
            with pytest.raises(RuntimeError, match="Stripe is not configured"):
                PaymentGatewayService._require_stripe()

    def test_stripe_configured_returns_module(self):
        mock_stripe = MagicMock()
        with patch("app.services.payment_gateway._get_stripe", return_value=mock_stripe):
            assert PaymentGatewayService._require_stripe() is mock_stripe


class TestCheckoutSession:
    """Checkout Session 创建测试"""

    def setup_method(self):
        self.svc = PaymentGatewayService()

    @pytest.mark.asyncio
    async def test_create_checkout_success(self):
        mock_stripe = MagicMock()
        mock_session = MagicMock(url="https://checkout.stripe.com/xxx", id="cs_123")
        mock_stripe.checkout.Session.create.return_value = mock_session
        mock_stripe.Customer.create.return_value = MagicMock(id="cus_123")

        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = [{"stripe_customer_id": None, "name": "Test Tenant"}]
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute = AsyncMock(return_value=resp)
        mock_db.table.return_value.update.return_value.eq.return_value.execute = AsyncMock()

        with (
            patch("app.services.payment_gateway._get_stripe", return_value=mock_stripe),
            patch.object(PaymentGatewayService, "_get_db", return_value=mock_db),
            patch("app.services.payment_gateway._get_plan_price_map", return_value={"starter": "price_starter"}),
        ):
            result = await self.svc.create_checkout_session(
                "tenant-1", "starter", "https://ok", "https://cancel"
            )
            assert result["url"] == "https://checkout.stripe.com/xxx"
            assert result["session_id"] == "cs_123"

    @pytest.mark.asyncio
    async def test_unknown_plan_raises(self):
        mock_stripe = MagicMock()
        with (
            patch("app.services.payment_gateway._get_stripe", return_value=mock_stripe),
            patch("app.services.payment_gateway._get_plan_price_map", return_value={"starter": "price_s"}),
        ):
            with pytest.raises(ValueError, match="Unknown plan"):
                await self.svc.create_checkout_session("t-1", "nonexistent", "u", "u")


class TestSubscription:
    """订阅管理测试"""

    def setup_method(self):
        self.svc = PaymentGatewayService()

    @pytest.mark.asyncio
    async def test_cancel_subscription(self):
        mock_stripe = MagicMock()
        mock_sub = MagicMock(id="sub_1", status="active", cancel_at_period_end=True)
        mock_stripe.Subscription.modify.return_value = mock_sub

        with patch("app.services.payment_gateway._get_stripe", return_value=mock_stripe):
            result = await self.svc.cancel_subscription("sub_1")
            assert result["cancel_at_period_end"] is True

    @pytest.mark.asyncio
    async def test_get_subscription_status(self):
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = [{"tenant_id": "t-1", "status": "active", "stripe_subscription_id": "sub_1"}]
        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute = AsyncMock(return_value=resp)

        with patch.object(PaymentGatewayService, "_get_db", return_value=mock_db):
            result = await self.svc.get_subscription_status("t-1")
            assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_subscription_no_db(self):
        with patch.object(PaymentGatewayService, "_get_db", return_value=None):
            result = await self.svc.get_subscription_status("t-1")
            assert result is None


class TestWebhook:
    """Webhook 处理测试"""

    def setup_method(self):
        self.svc = PaymentGatewayService()

    @pytest.mark.asyncio
    async def test_handle_known_event(self):
        mock_stripe = MagicMock()
        mock_event = {
            "type": "invoice.paid",
            "id": "evt_1",
            "data": {"object": {"metadata": {"tenant_id": "t-1"}, "subscription": "sub_1"}},
        }
        mock_stripe.Webhook.construct_event.return_value = mock_event

        mock_settings = MagicMock()
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

        with (
            patch("app.services.payment_gateway._get_stripe", return_value=mock_stripe),
            patch("app.core.config.settings", mock_settings),
        ):
            result = await self.svc.handle_webhook(b"payload", "sig_test")
            assert result["event_type"] == "invoice.paid"
            assert result["handled"] is True

    @pytest.mark.asyncio
    async def test_handle_unknown_event(self):
        mock_stripe = MagicMock()
        mock_event = {"type": "unknown.event", "data": {"object": {}}}
        mock_stripe.Webhook.construct_event.return_value = mock_event

        mock_settings = MagicMock()
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

        with (
            patch("app.services.payment_gateway._get_stripe", return_value=mock_stripe),
            patch("app.core.config.settings", mock_settings),
        ):
            result = await self.svc.handle_webhook(b"payload", "sig")
            assert result["handled"] is False


class TestUsageRecord:
    """用量计费测试"""

    def setup_method(self):
        self.svc = PaymentGatewayService()

    @pytest.mark.asyncio
    async def test_create_usage_record(self):
        mock_stripe = MagicMock()
        mock_record = MagicMock(id="mbur_1", quantity=100, timestamp=1700000000)
        mock_stripe.SubscriptionItem.create_usage_record.return_value = mock_record

        with patch("app.services.payment_gateway._get_stripe", return_value=mock_stripe):
            result = await self.svc.create_usage_record("si_1", 100)
            assert result["quantity"] == 100
