"""国内支付 API 端点"""

import logging
import os

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_list, api_success
from app.services.payment_service import payment_service

# 支付回调签名密钥 (微信/支付宝各自的 API 密钥用于验签)
_PAYMENT_CALLBACK_TOKEN = os.getenv("PAYMENT_CALLBACK_TOKEN", "")

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["Payments"])


@router.post("/create-order")
async def create_order(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建支付订单"""
    try:
        body = await req.json()
        plan_id = body.get("plan_id")
        payment_method = body.get("payment_method")
        amount = body.get("amount")

        if not plan_id or not payment_method:
            raise api_error(
                ErrorCode.VALIDATION_MISSING_FIELD,
                "plan_id 和 payment_method 为必填字段",
            )

        if not amount or float(amount) <= 0:
            raise api_error(
                ErrorCode.VALIDATION_INVALID_INPUT,
                "金额必须大于 0",
            )

        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        order = await payment_service.create_order(org_id, plan_id, payment_method, float(amount), db=db)
        return api_success(data={"order": order})
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "支付参数校验失败")
    except Exception as e:
        logger.error(f"Create order error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "支付操作失败")


@router.get("/orders")
async def list_orders(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取订单列表"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        result = await payment_service.list_orders(org_id, page, page_size, db=db)
        return api_list(
            items=result["orders"],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
        )
    except Exception as e:
        logger.error(f"List orders error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "支付操作失败")


@router.get("/orders/{order_id}")
async def get_order(
    order_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """查询订单详情"""
    try:
        db = getattr(req.state, "db", None)
        order = await payment_service.get_order_status(order_id, db=db)
        if order.get("error"):
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, order["error"])
        return api_success(data={"order": order})
    except Exception as e:
        logger.error(f"Get order error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "支付操作失败")


@router.get("/bank-info")
async def get_bank_transfer_info(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    plan_id: str = Query("professional", description="订阅计划 ID"),
):
    """获取对公转账信息"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        info = await payment_service.get_bank_transfer_info(org_id, plan_id)
        return api_success(data={"bank_info": info})
    except Exception as e:
        logger.error(f"Bank info error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "支付操作失败")


@router.post("/callback/{platform}")
async def payment_callback(
    platform: str,
    req: Request,
):
    """处理支付回调（微信/支付宝）- 需验证回调签名"""
    try:
        # 基本回调签名验证：要求配置 PAYMENT_CALLBACK_TOKEN
        if _PAYMENT_CALLBACK_TOKEN:
            provided = req.headers.get("X-Payment-Token", "")
            if provided != _PAYMENT_CALLBACK_TOKEN:
                logger.warning(f"Payment callback rejected: invalid token, platform={platform}, ip={req.client.host if req.client else 'unknown'}")
                raise api_error(ErrorCode.FORBIDDEN, "回调签名验证失败")

        body = await req.json()
        db = getattr(req.state, "db", None)
        result = await payment_service.handle_payment_callback(platform, body, db=db)
        return api_success(data=result)
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Payment callback error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "支付操作失败")


@router.post("/invoice")
async def request_invoice(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """申请增值税发票"""
    try:
        body = await req.json()
        order_id = body.get("order_id")
        invoice_info = body.get("invoice_info")

        if not order_id or not invoice_info:
            raise api_error(
                ErrorCode.VALIDATION_MISSING_FIELD,
                "order_id 和 invoice_info 为必填字段",
            )

        db = getattr(req.state, "db", None)
        result = await payment_service.generate_invoice_request(order_id, invoice_info, db=db)
        return api_success(data={"invoice_request": result})
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "支付参数校验失败")
    except Exception as e:
        logger.error(f"Invoice request error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "支付操作失败")
