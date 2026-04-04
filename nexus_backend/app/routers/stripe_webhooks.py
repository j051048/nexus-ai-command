"""Stripe Webhooks API 端点"""

import json
import logging

from fastapi import APIRouter, Header, Request, Response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])

# 延迟导入以避免可选依赖缺失导致启动失败
try:
    from app.services.payment_gateway import payment_gateway
except ImportError:
    logger.warning("Stripe payment gateway not available (missing dependencies)")
    payment_gateway = None


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
):
    """处理 Stripe 回调"""
    if not stripe_signature:
        return Response(content='{"error": "Missing Stripe-Signature"}', status_code=400, media_type="application/json")

    if not payment_gateway:
        return Response(
            content='{"error": "Payment gateway service unavailable"}', status_code=503, media_type="application/json"
        )

    try:
        payload = await request.body()
        # 验证并处理 Webhook
        _event = await payment_gateway.handle_webhook(payload, stripe_signature)
        return Response(content='{"status": "success"}', status_code=200, media_type="application/json")
    except ValueError as e:
        logger.error(f"Stripe webhook payload error: {e}")
        return Response(content=json.dumps({"error": str(e)}), status_code=400, media_type="application/json")
    except Exception as e:
        logger.error(f"Stripe webhook processing error: {e}")
        return Response(content=json.dumps({"error": "Internal server error"}), status_code=500, media_type="application/json")
