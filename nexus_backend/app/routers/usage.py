"""
P1 Optimization: Usage and Model Information Endpoints
Provides token usage tracking and model pricing information.
"""

import logging
from fastapi import APIRouter, Depends, Request
from app.core.auth import get_current_user_id
from app.services.token_service import usage_tracker, MODEL_MAPPING
from app.core.errors import api_success, api_error, ErrorCode
from app.models.schemas import StandardResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/usage", tags=["Usage"])


@router.get("/current", response_model=StandardResponse)
async def get_usage(user_id: str = Depends(get_current_user_id)):
    """
    Get current user's token usage and limits for today.
    """
    summary = usage_tracker.get_usage_summary(user_id)
    return api_success(data=summary)


@router.get("/models", response_model=StandardResponse)
async def get_available_models():
    """
    Get list of available AI models with pricing information.
    """
    models = []
    for model_name, pricing in MODEL_MAPPING.items():
        input_price, output_price = pricing.value
        models.append(
            {
                "name": model_name,
                "input_price_per_1m": input_price,
                "output_price_per_1m": output_price,
            }
        )

    sorted_models = sorted(models, key=lambda x: x["input_price_per_1m"])
    return api_success(data=sorted_models)


@router.get("/history", response_model=StandardResponse)
async def get_usage_history(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    days: int = 7,
):
    """
    Get usage history for the past N days.
    #53: Real DB query replacing stub.
    """
    days = min(max(1, days), 90)
    client = getattr(req.state, "db", None)

    if not client:
        return api_success(
            data={
                "current_day": usage_tracker.get_usage_summary(user_id),
                "history": [],
                "note": "Database unavailable, showing current session only.",
            }
        )

    try:
        res = await client.table("user_token_usage").select(
            "date, total_tokens, estimated_cost_usd, request_count"
        ).eq("user_id", user_id).order(
            "date", desc=True
        ).limit(days).execute()

        history = []
        for row in res.data or []:
            history.append({
                "date": row.get("date"),
                "tokens": row.get("total_tokens", 0),
                "cost_usd": float(row.get("estimated_cost_usd", 0)),
                "requests": row.get("request_count", 0),
            })

        return api_success(data={
            "current_day": usage_tracker.get_usage_summary(user_id),
            "history": history,
            "period_days": days,
        })
    except Exception as e:
        logger.error(f"Usage history query failed: {e}")
        return api_success(
            data={
                "current_day": usage_tracker.get_usage_summary(user_id),
                "history": [],
                "note": "Historical data query failed.",
            }
        )


@router.get("/cost-report", response_model=StandardResponse)
async def get_cost_report(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    days: int = 30,
):
    """
    #30 LLM Cost Attribution: Get cost breakdown by department and project.
    """
    org_id = getattr(req.state, "org_id", None) or "default"
    client = getattr(req.state, "db", None)
    try:
        report = await usage_tracker.get_cost_report(org_id, days=days, db=client)
        return api_success(data=report)
    except Exception as e:
        logger.error(f"Cost report failed: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
