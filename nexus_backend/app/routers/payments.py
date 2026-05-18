"""Domestic payment API endpoints."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_list, api_success
from app.services.payment_service import payment_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["Payments"])

_PAYMENT_CALLBACK_TOKEN = os.getenv("PAYMENT_CALLBACK_TOKEN", "")


def _get_org_id(req: Request) -> str:
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "当前账号未关联组织")
    return str(org_id)


@router.get("/methods")
async def list_payment_methods(user_id: str = Depends(get_current_user_id)):
    """Return payment methods after environment gating."""
    return api_success(data={"methods": payment_service.get_payment_methods()})


@router.post("/create-order")
async def create_order(req: Request, user_id: str = Depends(get_current_user_id)):
    """Create a payment order."""
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
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "金额必须大于 0")

        order = await payment_service.create_order(
            _get_org_id(req),
            str(plan_id),
            str(payment_method),
            float(amount),
            db=getattr(req.state, "db", None),
        )
        return api_success(data={"order": order})
    except ValueError as exc:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(exc))
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise
        logger.error("Create payment order error: %s", exc)
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "支付操作失败")


@router.get("/orders")
async def list_orders(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List payment orders for the current organization."""
    try:
        result = await payment_service.list_orders(
            _get_org_id(req),
            page,
            page_size,
            db=getattr(req.state, "db", None),
        )
        return api_list(
            items=result["orders"],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
        )
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise
        logger.error("List payment orders error: %s", exc)
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "支付操作失败")


@router.get("/orders/{order_id}")
async def get_order(
    order_id: str, req: Request, user_id: str = Depends(get_current_user_id)
):
    """Get payment order details."""
    try:
        order = await payment_service.get_order_status(
            order_id, db=getattr(req.state, "db", None)
        )
        if order.get("error"):
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, order["error"])
        if str(
            order.get("organization_id", getattr(req.state, "org_id", ""))
        ) != _get_org_id(req):
            raise api_error(ErrorCode.FORBIDDEN, "无权访问该订单")
        return api_success(data={"order": order})
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise
        logger.error("Get payment order error: %s", exc)
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "支付操作失败")


@router.get("/bank-info")
async def get_bank_transfer_info(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    plan_id: str = Query("professional", description="订阅计划 ID"),
):
    """Return bank transfer information."""
    try:
        info = await payment_service.get_bank_transfer_info(_get_org_id(req), plan_id)
        return api_success(data={"bank_info": info})
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise
        logger.error("Get bank info error: %s", exc)
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "支付操作失败")


@router.post("/callback/{platform}")
async def payment_callback(platform: str, req: Request):
    """Handle provider callbacks after token verification."""
    try:
        if not _PAYMENT_CALLBACK_TOKEN:
            logger.error("PAYMENT_CALLBACK_TOKEN is not configured; rejecting callback")
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "支付回调未配置签名密钥")

        provided = req.headers.get("X-Payment-Token", "")
        if provided != _PAYMENT_CALLBACK_TOKEN:
            logger.warning(
                "Payment callback rejected: invalid token, platform=%s, ip=%s",
                platform,
                req.client.host if req.client else "unknown",
            )
            raise api_error(ErrorCode.FORBIDDEN, "回调签名验证失败")

        result = await payment_service.handle_payment_callback(
            platform,
            await req.json(),
            db=getattr(req.state, "db", None),
        )
        return api_success(data=result)
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise
        logger.error("Payment callback error: %s", exc)
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "支付操作失败")


@router.post("/invoice")
async def request_invoice(req: Request, user_id: str = Depends(get_current_user_id)):
    """Create an invoice request for an order."""
    try:
        body = await req.json()
        order_id = body.get("order_id")
        invoice_info = body.get("invoice_info")
        if not order_id or not invoice_info:
            raise api_error(
                ErrorCode.VALIDATION_MISSING_FIELD,
                "order_id 和 invoice_info 为必填字段",
            )

        result = await payment_service.generate_invoice_request(
            str(order_id),
            dict(invoice_info),
            db=getattr(req.state, "db", None),
        )
        return api_success(data={"invoice_request": result})
    except ValueError as exc:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(exc))
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise
        logger.error("Invoice request error: %s", exc)
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "支付操作失败")
