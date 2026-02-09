"""
P1 Optimization: Usage and Model Information Endpoints
Provides token usage tracking and model pricing information.
"""
from fastapi import APIRouter, Depends
from app.core.auth import get_current_user_id
from app.services.token_service import usage_tracker, MODEL_MAPPING

router = APIRouter(prefix="/api", tags=["Usage"])


@router.get("/usage")
async def get_usage(user_id: str = Depends(get_current_user_id)):
    """
    Get current user's token usage and limits for today.
    
    Returns:
        - date: Current date
        - tokens_used: Total tokens used today
        - tokens_limit: Daily token limit
        - tokens_remaining: Remaining tokens for today
        - cost_usd: Estimated cost in USD
        - cost_limit_usd: Daily cost limit
        - requests: Number of requests made today
        - requests_limit: Daily request limit
    """
    summary = usage_tracker.get_usage_summary(user_id)
    return {
        "success": True,
        "data": summary
    }


@router.get("/models")
async def get_available_models():
    """
    Get list of available AI models with pricing information.
    
    Returns list of models with:
        - name: Model identifier
        - input_price_per_1m: Cost per 1M input tokens (USD)
        - output_price_per_1m: Cost per 1M output tokens (USD)
    """
    models = []
    for model_name, pricing in MODEL_MAPPING.items():
        input_price, output_price = pricing.value
        models.append({
            "name": model_name,
            "input_price_per_1m": input_price,
            "output_price_per_1m": output_price
        })
    
    return {
        "success": True,
        "models": sorted(models, key=lambda x: x["input_price_per_1m"])
    }


@router.get("/usage/history")
async def get_usage_history(user_id: str = Depends(get_current_user_id), days: int = 7):
    """
    Get usage history for the past N days.
    Note: This is a placeholder - actual implementation would require persistent storage.
    """
    # TODO: Implement with database storage
    return {
        "success": True,
        "message": "Usage history requires persistent storage (Redis/Database)",
        "data": {
            "current_day": usage_tracker.get_usage_summary(user_id)
        }
    }