"""
国内支付服务

支持对公转账（主要方式）、微信支付、支付宝支付。
微信/支付宝当前为预留接口，返回 mock 数据。
"""

import logging
import os
import uuid
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# 环境变量 (预留真实 API 密钥配置)
_WECHAT_APP_ID = os.getenv("WECHAT_PAY_APP_ID", "")
_WECHAT_MCH_ID = os.getenv("WECHAT_PAY_MCH_ID", "")
_WECHAT_API_KEY = os.getenv("WECHAT_PAY_API_KEY", "")
_ALIPAY_APP_ID = os.getenv("ALIPAY_APP_ID", "")
_ALIPAY_PRIVATE_KEY = os.getenv("ALIPAY_PRIVATE_KEY", "")

_IS_MOCK = not bool(_WECHAT_APP_ID and _WECHAT_MCH_ID)


def _generate_order_no() -> str:
    """生成唯一订单号: NX + 日期 + 随机串"""
    now = datetime.now(UTC)
    return f"NX{now.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"


# 订阅计划定价（人民币）
PLAN_PRICING = {
    "starter": {"name": "基础版", "monthly": 199, "yearly": 1990},
    "professional": {"name": "专业版", "monthly": 699, "yearly": 6990},
    "enterprise": {"name": "企业版", "monthly": 1999, "yearly": 19990},
}


class PaymentService:
    """国内支付服务"""

    PAYMENT_METHODS = {
        "bank_transfer": {"name": "对公转账", "description": "银行对公转账（主要方式）"},
        "wechat_pay": {"name": "微信支付", "description": "微信扫码支付"},
        "alipay": {"name": "支付宝", "description": "支付宝扫码支付"},
    }

    def __init__(self):
        self._orders_cache: dict[str, dict] = {}

    # ─── 创建订单 ──────────────────────────────────────────

    async def create_order(
        self,
        org_id: str,
        plan_id: str,
        payment_method: str,
        amount: float,
        db=None,
    ) -> dict:
        """创建支付订单"""
        if payment_method not in self.PAYMENT_METHODS:
            raise ValueError(f"不支持的支付方式: {payment_method}")

        order_no = _generate_order_no()
        plan_info = PLAN_PRICING.get(plan_id, {})

        order = {
            "id": str(uuid.uuid4()),
            "organization_id": org_id,
            "order_no": order_no,
            "plan_id": plan_id,
            "plan_name": plan_info.get("name", plan_id),
            "payment_method": payment_method,
            "amount": amount,
            "currency": "CNY",
            "status": "pending",
            "invoice_status": "none",
            "metadata": {},
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        # 持久化到数据库
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
            except Exception as e:
                logger.warning(f"Failed to persist payment order: {e}")

        # 内存缓存
        self._orders_cache[order_no] = order
        logger.info(f"Order created: {order_no} method={payment_method} amount={amount}")

        # 根据支付方式生成支付信息
        payment_info = {}
        if payment_method == "bank_transfer":
            payment_info = await self.get_bank_transfer_info(org_id, plan_id)
            payment_info["order_no"] = order_no
            payment_info["amount"] = amount
        elif payment_method == "wechat_pay":
            payment_info = await self.create_wechat_payment(
                order_no, amount, f"Nexus AI - {plan_info.get('name', plan_id)}"
            )
        elif payment_method == "alipay":
            payment_info = await self.create_alipay_payment(
                order_no, amount, f"Nexus AI - {plan_info.get('name', plan_id)}"
            )

        return {**order, "payment_info": payment_info}

    # ─── 微信支付 ──────────────────────────────────────────

    async def create_wechat_payment(self, order_id: str, amount: float, description: str) -> dict:
        """
        创建微信支付（返回支付二维码 URL）。
        预留接口，当前返回 mock。真实环境需要对接微信支付 V3 API。
        """
        if _IS_MOCK:
            return {
                "platform": "wechat_pay",
                "status": "mock",
                "qr_code_url": f"https://mock-wechat-pay.example.com/qr/{order_id}",
                "message": "微信支付即将上线，当前为演示模式",
                "order_id": order_id,
                "amount": amount,
                "expire_minutes": 30,
                "_dev_mode": True,
            }

        # TODO: 真实微信支付统一下单 API
        # from wechatpay import WeChatPay
        # client = WeChatPay(app_id=_WECHAT_APP_ID, mch_id=_WECHAT_MCH_ID, api_key=_WECHAT_API_KEY)
        # result = client.unified_order(
        #     body=description,
        #     out_trade_no=order_id,
        #     total_fee=int(amount * 100),  # 分
        #     trade_type="NATIVE",
        #     notify_url=f"{os.getenv('API_BASE_URL')}/api/payments/callback/wechat",
        # )
        # return {"platform": "wechat_pay", "qr_code_url": result["code_url"], ...}

        return {
            "platform": "wechat_pay",
            "status": "unavailable",
            "message": "微信支付密钥未配置",
        }

    # ─── 支付宝支付 ─────────────────────────────────────────

    async def create_alipay_payment(self, order_id: str, amount: float, description: str) -> dict:
        """
        创建支付宝支付（返回支付页面 URL）。
        预留接口，当前返回 mock。真实环境需要对接支付宝开放平台 API。
        """
        if _IS_MOCK:
            return {
                "platform": "alipay",
                "status": "mock",
                "pay_url": f"https://mock-alipay.example.com/pay/{order_id}",
                "message": "支付宝支付即将上线，当前为演示模式",
                "order_id": order_id,
                "amount": amount,
                "expire_minutes": 30,
                "_dev_mode": True,
            }

        # TODO: 真实支付宝下单 API
        # from alipay import AliPay
        # client = AliPay(appid=_ALIPAY_APP_ID, app_private_key_string=_ALIPAY_PRIVATE_KEY, ...)
        # order_string = client.api_alipay_trade_page_pay(
        #     out_trade_no=order_id,
        #     total_amount=str(amount),
        #     subject=description,
        #     return_url=f"{os.getenv('FRONTEND_URL')}/payment/success",
        #     notify_url=f"{os.getenv('API_BASE_URL')}/api/payments/callback/alipay",
        # )
        # return {"platform": "alipay", "pay_url": f"https://openapi.alipay.com/gateway.do?{order_string}", ...}

        return {
            "platform": "alipay",
            "status": "unavailable",
            "message": "支付宝密钥未配置",
        }

    # ─── 支付回调 ──────────────────────────────────────────

    async def handle_payment_callback(self, platform: str, callback_data: dict, db=None) -> dict:
        """处理支付回调（微信/支付宝）"""
        logger.info(f"Payment callback from {platform}: {callback_data}")

        if platform == "wechat":
            # TODO: 验证微信签名
            order_no = callback_data.get("out_trade_no", "")
            trade_state = callback_data.get("trade_state", "")
            success = trade_state == "SUCCESS"
        elif platform == "alipay":
            # TODO: 验证支付宝签名
            order_no = callback_data.get("out_trade_no", "")
            trade_status = callback_data.get("trade_status", "")
            success = trade_status == "TRADE_SUCCESS"
        else:
            return {"success": False, "message": f"未知支付平台: {platform}"}

        if success and order_no:
            # 更新订单状态
            if order_no in self._orders_cache:
                self._orders_cache[order_no]["status"] = "paid"
                self._orders_cache[order_no]["paid_at"] = datetime.now(UTC).isoformat()

            if db:
                try:
                    await (
                        db.table("payment_orders")
                        .update(
                            {
                                "status": "paid",
                                "paid_at": datetime.now(UTC).isoformat(),
                            }
                        )
                        .eq("order_no", order_no)
                        .execute()
                    )
                except Exception as e:
                    logger.error(f"Failed to update order status: {e}")

            logger.info(f"Order {order_no} marked as paid via {platform}")
            return {"success": True, "order_no": order_no, "status": "paid"}

        return {"success": False, "message": "支付未成功"}

    # ─── 订单查询 ──────────────────────────────────────────

    async def get_order_status(self, order_id: str, db=None) -> dict:
        """查询订单状态"""
        # 先查缓存
        if order_id in self._orders_cache:
            return self._orders_cache[order_id]

        # 查数据库
        if db:
            try:
                res = await db.table("payment_orders").select("*").eq("id", order_id).maybe_single().execute()
                if res.data:
                    return res.data
            except Exception as e:
                logger.warning(f"Order query failed: {e}")

        return {"error": "订单不存在", "order_id": order_id}

    async def list_orders(self, org_id: str, page: int = 1, page_size: int = 20, db=None) -> dict:
        """获取组织的订单列表"""
        orders = []
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
            except Exception as e:
                logger.warning(f"Order list query failed: {e}")

        # 如果无数据返回空列表
        if not orders:
            return {"orders": [], "total": 0, "page": page, "page_size": page_size}

        return {"orders": orders, "total": total, "page": page, "page_size": page_size}

    # ─── 发票申请 ──────────────────────────────────────────

    async def generate_invoice_request(self, order_id: str, invoice_info: dict, db=None) -> dict:
        """生成增值税发票申请"""
        required_fields = ["company_name", "tax_number"]
        for field in required_fields:
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
                        {
                            "invoice_status": "requested",
                            "invoice_info": invoice_info,
                        }
                    )
                    .eq("id", order_id)
                    .execute()
                )
            except Exception as e:
                logger.warning(f"Invoice request update failed: {e}")

        # 更新缓存
        for order in self._orders_cache.values():
            if order.get("id") == order_id:
                order["invoice_status"] = "requested"
                order["invoice_info"] = invoice_info

        logger.info(f"Invoice requested for order {order_id}")
        return invoice_request

    # ─── 对公转账信息 ─────────────────────────────────────

    async def get_bank_transfer_info(self, org_id: str, plan_id: str) -> dict:
        """获取对公转账信息"""
        plan_info = PLAN_PRICING.get(plan_id, {})
        return {
            "bank_name": "中国工商银行",
            "branch": "北京市海淀区中关村支行",
            "account_name": "Nexus AI 科技有限公司",
            "account_number": "待配置",
            "reference": f"ORG-{org_id[:8]}",
            "plan_name": plan_info.get("name", plan_id),
            "amount": plan_info.get("monthly", "根据订阅计划"),
            "note": "请在转账备注中填写参考号(reference)，以便我们快速确认您的付款。",
        }


# Global instance
payment_service = PaymentService()
