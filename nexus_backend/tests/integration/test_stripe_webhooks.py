"""
Stripe Webhooks 路由集成测试
覆盖: 正常处理、缺少签名、服务不可用、payload 错误
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestStripeWebhook:
    """POST /api/webhooks/stripe"""

    @pytest.mark.asyncio
    async def test_missing_signature_returns_400(self, async_client):
        resp = await async_client.post("/api/webhooks/stripe", content=b"test")
        assert resp.status_code == 400
        assert "Stripe-Signature" in resp.text or "Missing" in resp.text

    @pytest.mark.asyncio
    async def test_gateway_unavailable_returns_503(self, async_client):
        with patch("app.routers.stripe_webhooks.payment_gateway", None):
            resp = await async_client.post(
                "/api/webhooks/stripe",
                content=b"test",
                headers={"stripe-signature": "sig_test"},
            )
            assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_successful_webhook(self, async_client):
        mock_gw = AsyncMock()
        mock_gw.handle_webhook.return_value = {"event_type": "invoice.paid", "handled": True}

        with patch("app.routers.stripe_webhooks.payment_gateway", mock_gw):
            resp = await async_client.post(
                "/api/webhooks/stripe",
                content=b'{"type":"invoice.paid"}',
                headers={"stripe-signature": "sig_valid"},
            )
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_value_error_returns_400(self, async_client):
        mock_gw = AsyncMock()
        mock_gw.handle_webhook.side_effect = ValueError("Invalid payload")

        with patch("app.routers.stripe_webhooks.payment_gateway", mock_gw):
            resp = await async_client.post(
                "/api/webhooks/stripe",
                content=b"bad",
                headers={"stripe-signature": "sig_bad"},
            )
            assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_unexpected_error_returns_500(self, async_client):
        mock_gw = AsyncMock()
        mock_gw.handle_webhook.side_effect = Exception("Unexpected")

        with patch("app.routers.stripe_webhooks.payment_gateway", mock_gw):
            resp = await async_client.post(
                "/api/webhooks/stripe",
                content=b"data",
                headers={"stripe-signature": "sig_err"},
            )
            assert resp.status_code == 500
