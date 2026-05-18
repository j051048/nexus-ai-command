"""Domestic payment service for the non-AI SaaS billing flow.

For the first production launch, bank transfer is the only enabled domestic
payment method. WeChat Pay and Alipay stay hidden/blocked until real provider
credentials, signature verification, and callback reconciliation are implemented.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def _env_is_production() -> bool:
    return os.getenv("ENV", "").lower() in {"production", "prod"}


def _enabled_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _generate_order_no() -> str:
    now = datetime.now(UTC)
    return f"NX{now.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"


PLAN_PRICING: dict[str, dict[str, Any]] = {
    "starter": {"name": "基础版", "monthly": 199, "yearly": 1990},
    "professional": {"name": "专业版", "monthly": 699, "yearly": 6990},
    "enterprise": {"name": "企业版", "monthly": 1999, "yearly": 19990},
}


class PaymentService:
    """Payment service with production-safe method gating."""

    PAYMENT_METHODS: dict[str, dict[str, Any]] = {
        "bank_transfer": {
            "name": "对公转账",
            "description": "银行对公转账，首发生产环境唯一启用方式",
            "available": True,
        },
        "wechat_pay": {
            "name": "微信支付",
            "description": "待真实微信支付 V3 对接后启用",
            "available": False,
        },
        "alipay": {
            "name": "支付宝",
            "description": "待真实支付宝开放平台对接后启用",
            "available": False,
        },
    }

    def __init__(self) -> None:
        self._orders_cache: dict[str, dict[str, Any]] = {}

    def is_method_available(self, payment_method: str) -> bool:
        if payment_method == "bank_transfer":
            return True
        if payment_method == "wechat_pay":
            return (not _env_is_production()) and _enabled_flag(
                "PAYMENT_ENABLE_WECHAT_SANDBOX"
            )
        if payment_method == "alipay":
            return (not _env_is_production()) and _enabled_flag(
                "PAYMENT_ENABLE_ALIPAY_SANDBOX"
            )
        return False

    def get_payment_methods(self) -> list[dict[str, Any]]:
        return [
            {**meta, "id": method, "available": self.is_method_available(method)}
            for method, meta in self.PAYMENT_METHODS.items()
        ]

    async def create_order(
        self,
        org_id: str,
        plan_id: str,
        payment_method: str,
        amount: float,
        db=None,
    ) -> dict[str, Any]:
        """Create a payment order after method and amount validation."""
        if payment_method not in self.PAYMENT_METHODS:
            raise ValueError(f"不支持的支付方式: {payment_method}")
        if not self.is_method_available(payment_method):
            raise ValueError(
                f"{self.PAYMENT_METHODS[payment_method]['name']}尚未在当前环境启用"
            )
        if plan_id not in PLAN_PRICING:
            raise ValueError(f"未知订阅计划: {plan_id}")
        if amount <= 0:
            raise ValueError("金额必须大于 0")

        order_no = _generate_order_no()
        plan_info = PLAN_PRICING[plan_id]
        order: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "organization_id": org_id,
            "order_no": order_no,
            "plan_id": plan_id,
            "plan_name": plan_info["name"],
            "payment_method": payment_method,
            "amount": amount,
            "currency": "CNY",
            "status": "pending",
            "invoice_status": "none",
            "metadata": {},
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        if db:
            try:
                res = (
                    await db.table("payment_orders")
                    .insert(
                        {
                            "organization_id": org_id,
                            "order_no": order_no,
                            "plan_id": plan_id,
                            "payment_method": payment_method,
                            "amount": amount,
                            "currency": "CNY",
                            "status": "pending",
                        }
                    )
                    .execute()
                )
                if res.data:
                    order["id"] = res.data[0].get("id", order["id"])
            except Exception as exc:  # pragma: no cover - external DB failure path
                logger.warning("Failed to persist payment order: %s", exc)

        self._orders_cache[order_no] = order
        logger.info(
            "Payment order created: %s method=%s amount=%s",
            order_no,
            payment_method,
            amount,
        )

        payment_info: dict[str, Any] = {}
        if payment_method == "bank_transfer":
            payment_info = await self.get_bank_transfer_info(org_id, plan_id)
            payment_info["order_no"] = order_no
            payment_info["amount"] = amount

        return {**order, "payment_info": payment_info}

    async def handle_payment_callback(
        self, platform: str, callback_data: dict[str, Any], db=None
    ) -> dict[str, Any]:
        """Reject unimplemented domestic payment callbacks in production."""
        if platform not in {"wechat", "alipay"}:
            return {"success": False, "message": f"未知支付平台: {platform}"}
        if _env_is_production():
            logger.warning(
                "Rejected %s callback because provider is not enabled in production",
                platform,
            )
            return {"success": False, "message": "该支付渠道尚未在生产环境启用"}

        order_no = callback_data.get("out_trade_no", "")
        success = (
            callback_data.get("trade_state") == "SUCCESS"
            or callback_data.get("trade_status") == "TRADE_SUCCESS"
        )
        if success and order_no:
            if order_no in self._orders_cache:
                self._orders_cache[order_no]["status"] = "paid"
                self._orders_cache[order_no]["paid_at"] = datetime.now(UTC).isoformat()

            if db:
                try:
                    await (
                        db.table("payment_orders")
                        .update(
                            {"status": "paid", "paid_at": datetime.now(UTC).isoformat()}
                        )
                        .eq("order_no", order_no)
                        .execute()
                    )
                except Exception as exc:  # pragma: no cover - external DB failure path
                    logger.error("Failed to update order status: %s", exc)
            return {"success": True, "order_no": order_no, "status": "paid"}

        return {"success": False, "message": "支付未成功"}

    async def get_order_status(self, order_id: str, db=None) -> dict[str, Any]:
        if order_id in self._orders_cache:
            return self._orders_cache[order_id]

        if db:
            try:
                res = (
                    await db.table("payment_orders")
                    .select("*")
                    .eq("id", order_id)
                    .maybe_single()
                    .execute()
                )
                if res.data:
                    return res.data
            except Exception as exc:  # pragma: no cover - external DB failure path
                logger.warning("Order query failed: %s", exc)

        return {"error": "订单不存在", "order_id": order_id}

    async def list_orders(
        self, org_id: str, page: int = 1, page_size: int = 20, db=None
    ) -> dict[str, Any]:
        orders: list[dict[str, Any]] = []
        total = 0
        if db:
            try:
                offset = (page - 1) * page_size
                res = (
                    await db.table("payment_orders")
                    .select("*", count="exact")
                    .eq("organization_id", org_id)
                    .order("created_at", desc=True)
                    .range(offset, offset + page_size - 1)
                    .execute()
                )
                orders = res.data or []
                total = res.count or len(orders)
            except Exception as exc:  # pragma: no cover - external DB failure path
                logger.warning("Order list query failed: %s", exc)

        return {"orders": orders, "total": total, "page": page, "page_size": page_size}

    async def generate_invoice_request(
        self, order_id: str, invoice_info: dict[str, Any], db=None
    ) -> dict[str, Any]:
        for field in ["company_name", "tax_number"]:
            if not invoice_info.get(field):
                raise ValueError(f"发票信息缺少必填字段: {field}")

        invoice_request = {
            "order_id": order_id,
            "invoice_info": invoice_info,
            "status": "requested",
            "requested_at": datetime.now(UTC).isoformat(),
        }

        if db:
            try:
                await (
                    db.table("payment_orders")
                    .update(
                        {"invoice_status": "requested", "invoice_info": invoice_info}
                    )
                    .eq("id", order_id)
                    .execute()
                )
            except Exception as exc:  # pragma: no cover - external DB failure path
                logger.warning("Invoice request update failed: %s", exc)

        for order in self._orders_cache.values():
            if order.get("id") == order_id:
                order["invoice_status"] = "requested"
                order["invoice_info"] = invoice_info

        logger.info("Invoice requested for order %s", order_id)
        return invoice_request

    async def get_bank_transfer_info(self, org_id: str, plan_id: str) -> dict[str, Any]:
        plan_info = PLAN_PRICING.get(plan_id, {})
        account_number = os.getenv("BANK_ACCOUNT_NUMBER", "")
        result = {
            "bank_name": os.getenv("BANK_NAME", "") or "待配置",
            "branch": os.getenv("BANK_BRANCH", "") or "待配置",
            "account_name": os.getenv("BANK_ACCOUNT_NAME", "") or "待配置",
            "account_number": account_number or "待配置",
            "reference": f"ORG-{org_id[:8]}",
            "plan_name": plan_info.get("name", plan_id),
            "amount": plan_info.get("monthly", "根据订阅计划"),
            "note": "请在转账备注中填写参考号，便于财务快速确认付款。",
            "configured": bool(account_number),
        }
        if not account_number:
            result["mode"] = "configuration_required"
        return result


payment_service = PaymentService()
