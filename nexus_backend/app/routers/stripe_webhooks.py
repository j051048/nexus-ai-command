"""
Stripe Webhook endpoint.

POST /api/webhooks/stripe — receives Stripe events, verifies signature,
and delegates to PaymentGatewayService for idempotent processing.

No authentication required (Stripe sends webhooks directly).
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Stripe Webhooks"])


@router.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Process incoming Stripe webhook events.

    Stripe sends raw body + Stripe-Signature header.
    We verify the signature and dispatch to the payment gateway service.
    Idempotency is guaranteed by Stripe event IDs — duplicate events
    are safe because our handlers are upsert-based.
    """
    try:
        from app.services.payment_gateway import payment_gateway
    except Exception as exc:
        logger.error("Failed to import payment_gateway: %s", exc)
        return JSONResponse({"error": "service unavailable"}, status_code=503)

    # Read raw body (Stripe requires the raw bytes for signature verification)
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature", "")

    if not signature:
        return JSONResponse({"error": "Missing Stripe-Signature header"}, status_code=400)

    try:
        result = await payment_gateway.handle_webhook(payload, signature)
        return JSONResponse({"status": "ok", **result}, status_code=200)

    except RuntimeError as exc:
        # Stripe not configured
        logger.warning("Stripe webhook rejected: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=503)

    except ValueError as exc:
        # Invalid payload
        logger.warning("Stripe webhook invalid payload: %s", exc)
        return JSONResponse({"error": "Invalid payload"}, status_code=400)

    except Exception as exc:
        # Signature verification failure or other Stripe error
        error_name = type(exc).__name__
        logger.error("Stripe webhook processing error (%s): %s", error_name, exc)
        return JSONResponse({"error": "Webhook processing failed"}, status_code=400)
