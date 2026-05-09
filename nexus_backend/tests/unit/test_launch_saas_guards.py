"""Launch guards for the non-AI SaaS production surface."""

from __future__ import annotations

import pytest

from app.services.payment_service import PaymentService


@pytest.mark.asyncio
async def test_domestic_payment_mock_methods_are_blocked_in_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    service = PaymentService()

    assert service.is_method_available("bank_transfer") is True
    assert service.is_method_available("wechat_pay") is False
    assert service.is_method_available("alipay") is False

    with pytest.raises(ValueError, match="尚未在当前环境启用"):
        await service.create_order("org_12345678", "professional", "wechat_pay", 699)


@pytest.mark.asyncio
async def test_bank_transfer_order_uses_configured_bank_info(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("BANK_NAME", "测试银行")
    monkeypatch.setenv("BANK_BRANCH", "上海分行")
    monkeypatch.setenv("BANK_ACCOUNT_NAME", "测试科技有限公司")
    monkeypatch.setenv("BANK_ACCOUNT_NUMBER", "6222000000000000")

    service = PaymentService()
    order = await service.create_order("org_12345678", "professional", "bank_transfer", 699)

    assert order["payment_method"] == "bank_transfer"
    assert order["payment_info"]["bank_name"] == "测试银行"
    assert order["payment_info"]["configured"] is True
    assert order["payment_info"]["reference"] == "ORG-org_1234"
