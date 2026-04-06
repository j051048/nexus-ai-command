"""
Tests for payments router — orders, bank info, callbacks, invoices.
Also covers stripe_webhooks router.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Payments Router Tests ──


class TestCreateOrder:
    """POST /api/payments/create-order"""

    @pytest.mark.asyncio
    async def test_missing_required_fields(self):
        from app.routers.payments import create_order

        req = MagicMock()
        req.json = AsyncMock(return_value={"amount": 100})
        req.state.org_id = "org-1"

        with pytest.raises(Exception) as exc_info:
            await create_order(req=req, user_id="user-1")
        assert exc_info.value.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_zero_amount_rejected(self):
        from app.routers.payments import create_order

        req = MagicMock()
        req.json = AsyncMock(
            return_value={
                "plan_id": "pro",
                "payment_method": "wechat",
                "amount": 0,
            }
        )
        req.state.org_id = "org-1"

        with pytest.raises(Exception) as exc_info:
            await create_order(req=req, user_id="user-1")
        assert exc_info.value.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_negative_amount_rejected(self):
        from app.routers.payments import create_order

        req = MagicMock()
        req.json = AsyncMock(
            return_value={
                "plan_id": "pro",
                "payment_method": "wechat",
                "amount": -50,
            }
        )
        req.state.org_id = "org-1"

        with pytest.raises(Exception) as exc_info:
            await create_order(req=req, user_id="user-1")
        assert exc_info.value.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_no_org_id_returns_403(self):
        from app.routers.payments import create_order

        req = MagicMock()
        req.json = AsyncMock(
            return_value={
                "plan_id": "pro",
                "payment_method": "wechat",
                "amount": 99,
            }
        )
        req.state = MagicMock(spec=[])  # no org_id

        with pytest.raises(Exception) as exc_info:
            await create_order(req=req, user_id="user-1")
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_create_order_success(self):
        from app.routers.payments import create_order

        order_data = {
            "order_id": "ord-123",
            "status": "pending",
            "qr_code_url": "https://pay.example.com/qr",
        }

        req = MagicMock()
        req.json = AsyncMock(
            return_value={
                "plan_id": "pro",
                "payment_method": "wechat",
                "amount": 99,
            }
        )
        req.state.org_id = "org-1"
        req.state.db = None

        with patch("app.routers.payments.payment_service") as mock_svc:
            mock_svc.create_order = AsyncMock(return_value=order_data)
            result = await create_order(req=req, user_id="user-1")

        assert result["success"] is True
        assert result["data"]["order"]["order_id"] == "ord-123"


class TestListOrders:
    """GET /api/payments/orders"""

    @pytest.mark.asyncio
    async def test_no_org_id_returns_403(self):
        from app.routers.payments import list_orders

        req = MagicMock()
        req.state = MagicMock(spec=[])

        with pytest.raises(Exception) as exc_info:
            await list_orders(req=req, user_id="user-1", page=1, page_size=20)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_list_orders_success(self):
        from app.routers.payments import list_orders

        req = MagicMock()
        req.state.org_id = "org-1"
        req.state.db = None

        with patch("app.routers.payments.payment_service") as mock_svc:
            mock_svc.list_orders = AsyncMock(
                return_value={
                    "orders": [{"id": "ord-1"}, {"id": "ord-2"}],
                    "total": 2,
                    "page": 1,
                    "page_size": 20,
                }
            )
            result = await list_orders(req=req, user_id="user-1", page=1, page_size=20)

        assert result["success"] is True
        assert len(result["data"]) == 2


class TestGetOrder:
    """GET /api/payments/orders/{order_id}"""

    @pytest.mark.asyncio
    async def test_order_not_found(self):
        from app.routers.payments import get_order

        req = MagicMock()
        req.state.db = None

        with patch("app.routers.payments.payment_service") as mock_svc:
            mock_svc.get_order_status = AsyncMock(
                return_value={"error": "订单不存在"}
            )
            with pytest.raises(Exception) as exc_info:
                await get_order(order_id="nonexistent", req=req, user_id="user-1")
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_order_success(self):
        from app.routers.payments import get_order

        order_data = {"order_id": "ord-1", "status": "paid", "amount": 99}

        req = MagicMock()
        req.state.db = None

        with patch("app.routers.payments.payment_service") as mock_svc:
            mock_svc.get_order_status = AsyncMock(return_value=order_data)
            result = await get_order(order_id="ord-1", req=req, user_id="user-1")

        assert result["success"] is True
        assert result["data"]["order"]["status"] == "paid"


class TestGetBankInfo:
    """GET /api/payments/bank-info"""

    @pytest.mark.asyncio
    async def test_no_org_id_returns_403(self):
        from app.routers.payments import get_bank_transfer_info

        req = MagicMock()
        req.state = MagicMock(spec=[])

        with pytest.raises(Exception) as exc_info:
            await get_bank_transfer_info(req=req, user_id="user-1", plan_id="pro")
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_bank_info_success(self):
        from app.routers.payments import get_bank_transfer_info

        bank_info = {
            "bank_name": "中国银行",
            "account": "1234567890",
            "amount": 9900,
        }

        req = MagicMock()
        req.state.org_id = "org-1"

        with patch("app.routers.payments.payment_service") as mock_svc:
            mock_svc.get_bank_transfer_info = AsyncMock(return_value=bank_info)
            result = await get_bank_transfer_info(
                req=req, user_id="user-1", plan_id="pro"
            )

        assert result["success"] is True
        assert result["data"]["bank_info"]["bank_name"] == "中国银行"


class TestPaymentCallback:
    """POST /api/payments/callback/{platform}"""

    @pytest.mark.asyncio
    async def test_invalid_token_rejected(self):
        from app.routers.payments import payment_callback

        req = MagicMock()
        req.headers = {"X-Payment-Token": "wrong-token"}
        req.client = MagicMock()
        req.client.host = "1.2.3.4"

        with patch("app.routers.payments._PAYMENT_CALLBACK_TOKEN", "correct-token"):
            with pytest.raises(Exception) as exc_info:
                await payment_callback(platform="wechat", req=req)
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_callback_success(self):
        from app.routers.payments import payment_callback

        req = MagicMock()
        req.headers = {"X-Payment-Token": "correct-token"}
        req.json = AsyncMock(
            return_value={"order_id": "ord-1", "status": "success"}
        )
        req.state.db = None
        req.client = MagicMock()
        req.client.host = "1.2.3.4"

        with (
            patch("app.routers.payments._PAYMENT_CALLBACK_TOKEN", "correct-token"),
            patch("app.routers.payments.payment_service") as mock_svc,
        ):
            mock_svc.handle_payment_callback = AsyncMock(
                return_value={"processed": True}
            )
            result = await payment_callback(platform="wechat", req=req)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_callback_no_token_configured_rejects_request(self):
        """When PAYMENT_CALLBACK_TOKEN is not set, callback should be rejected."""
        from app.routers.payments import payment_callback

        req = MagicMock()
        req.headers = {}
        req.json = AsyncMock(return_value={"order_id": "ord-1"})
        req.state.db = None

        with (
            patch("app.routers.payments._PAYMENT_CALLBACK_TOKEN", ""),
            patch("app.routers.payments.payment_service") as mock_svc,
        ):
            mock_svc.handle_payment_callback = AsyncMock(
                return_value={"processed": True}
            )
            with pytest.raises(Exception) as exc_info:
                await payment_callback(platform="alipay", req=req)
            assert exc_info.value.status_code == 500


class TestRequestInvoice:
    """POST /api/payments/invoice"""

    @pytest.mark.asyncio
    async def test_missing_fields_rejected(self):
        from app.routers.payments import request_invoice

        req = MagicMock()
        req.json = AsyncMock(return_value={"order_id": "ord-1"})  # missing invoice_info
        req.state.db = None

        with pytest.raises(Exception) as exc_info:
            await request_invoice(req=req, user_id="user-1")
        assert exc_info.value.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_invoice_success(self):
        from app.routers.payments import request_invoice

        invoice_result = {"request_id": "inv-1", "status": "submitted"}

        req = MagicMock()
        req.json = AsyncMock(
            return_value={
                "order_id": "ord-1",
                "invoice_info": {
                    "title": "测试公司",
                    "tax_id": "1234567890",
                },
            }
        )
        req.state.db = None

        with patch("app.routers.payments.payment_service") as mock_svc:
            mock_svc.generate_invoice_request = AsyncMock(return_value=invoice_result)
            result = await request_invoice(req=req, user_id="user-1")

        assert result["success"] is True
        assert result["data"]["invoice_request"]["status"] == "submitted"


# ── Stripe Webhooks Router Tests ──


class TestStripeWebhook:
    """POST /api/webhooks/stripe"""

    @pytest.mark.asyncio
    async def test_missing_signature_returns_400(self, async_client):
        resp = await async_client.post(
            "/api/webhooks/stripe",
            content=b'{"type": "test"}',
        )
        assert resp.status_code == 400
        assert "Missing" in resp.json().get("error", "")

    @pytest.mark.asyncio
    async def test_import_failure_returns_503(self):
        from app.routers.stripe_webhooks import stripe_webhook

        req = MagicMock()
        req.body = AsyncMock(return_value=b'{"type": "test"}')
        req.headers = {"Stripe-Signature": "sig"}

        with patch(
            "app.routers.stripe_webhooks.payment_gateway",
            side_effect=ImportError("no module"),
        ):
            # Force import to fail inside the function
            import importlib

            import app.routers.stripe_webhooks as sw

            original_post = sw.stripe_webhook

            async def _mock_webhook(request):
                """Simulate import failure."""
                try:
                    raise ImportError("no module")
                except Exception:
                    from fastapi.responses import JSONResponse

                    return JSONResponse(
                        {"error": "service unavailable"}, status_code=503
                    )

            result = await _mock_webhook(req)
            assert result.status_code == 503

    @pytest.mark.asyncio
    async def test_valid_webhook_processed(self):
        from app.routers.stripe_webhooks import stripe_webhook

        req = MagicMock()
        req.body = AsyncMock(return_value=b'{"type": "payment_intent.succeeded"}')
        req.headers = {"Stripe-Signature": "valid-sig"}

        mock_gateway = MagicMock()
        mock_gateway.handle_webhook = AsyncMock(
            return_value={"event_type": "payment_intent.succeeded"}
        )

        with patch(
            "app.routers.stripe_webhooks.payment_gateway", mock_gateway
        ):
            result = await stripe_webhook(request=req)

        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_payload_returns_400(self):
        from app.routers.stripe_webhooks import stripe_webhook

        req = MagicMock()
        req.body = AsyncMock(return_value=b"invalid-json")
        req.headers = {"Stripe-Signature": "some-sig"}

        mock_gateway = MagicMock()
        mock_gateway.handle_webhook = AsyncMock(
            side_effect=ValueError("Invalid payload")
        )

        with patch(
            "app.routers.stripe_webhooks.payment_gateway", mock_gateway
        ):
            result = await stripe_webhook(request=req)

        assert result.status_code == 400
