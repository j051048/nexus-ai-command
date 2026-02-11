"""
P1 Optimization: Usage and Model Information Endpoints
Provides token usage tracking and model pricing information.
"""

from fastapi import APIRouter, Depends
from app.core.auth import get_current_user_id
from app.services.token_service import usage_tracker, MODEL_MAPPING
from app.core.errors import api_success
from app.models.schemas import StandardResponse

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
async def get_usage_history(user_id: str = Depends(get_current_user_id), days: int = 7):
    """
    Get usage history for the past N days.
    (Currently returns only current day as persistence is pending)
    """
    # Placeholder for future DB implementation
    return api_success(
        data={
            "current_day": usage_tracker.get_usage_summary(user_id),
            "note": "Historical data requires persistent storage integration.",
        }
    )
