"""
P1 Optimization: Usage and Model Information Endpoints
Provides token usage tracking and model pricing information.
"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.models.schemas import StandardResponse
from app.services.token_service import (
    MODEL_MAPPING,
    token_counter,
    usage_tracker,
)

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


# ---------------------------------------------------------------------------
# Token Estimation Endpoint
# ---------------------------------------------------------------------------

class EstimateRequest(BaseModel):
    """Request body for token estimation."""
    messages: list[dict]
    model: str = "gpt-4o"
    expected_output_ratio: float = 1.5  # Estimated output/input token ratio


@router.post("/estimate", response_model=StandardResponse)
async def estimate_tokens(
    body: EstimateRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Estimate token consumption and cost before sending a request.

    Returns input token count, estimated output tokens, total estimate,
    and projected cost so the frontend can warn the user before
    expensive operations.
    """
    input_tokens = token_counter.count_messages_tokens(body.messages, body.model)
    estimated_output = int(input_tokens * body.expected_output_ratio)
    estimated_total = input_tokens + estimated_output
    estimated_cost = token_counter.estimate_cost(input_tokens, estimated_output, body.model)

    # Check if this would exceed limits
    is_allowed, reason = usage_tracker.check_limits(user_id, estimated_total)

    return api_success(data={
        "input_tokens": input_tokens,
        "estimated_output_tokens": estimated_output,
        "estimated_total_tokens": estimated_total,
        "estimated_cost_usd": estimated_cost,
        "model": body.model,
        "within_limits": is_allowed,
        "limit_warning": reason if not is_allowed else None,
    })


# ---------------------------------------------------------------------------
# Monthly Quota Alert Endpoint
# ---------------------------------------------------------------------------

_ALERT_THRESHOLDS = [
    (1.0, "exhausted"),
    (0.95, "critical"),
    (0.80, "warning"),
    (0.0, "normal"),
]


@router.get("/quota-alert", response_model=StandardResponse)
async def get_quota_alert(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Get monthly quota usage percentage and alert level.

    Alert levels:
      - normal:    < 80%
      - warning:   80% - 95%
      - critical:  95% - 100%
      - exhausted: >= 100%
    """
    client = getattr(req.state, "db", None)

    # Aggregate current month usage from DB
    month_tokens = 0
    month_cost = 0.0
    month_requests = 0

    if client:
        try:
            import time
            current_month_start = time.strftime("%Y-%m-01")

            res = await client.table("user_token_usage").select(
                "total_tokens, estimated_cost_usd, request_count"
            ).eq("user_id", user_id).gte(
                "date", current_month_start
            ).execute()

            for row in res.data or []:
                month_tokens += row.get("total_tokens", 0)
                month_cost += float(row.get("estimated_cost_usd", 0))
                month_requests += row.get("request_count", 0)
        except Exception as e:
            logger.warning("Monthly usage query failed: %s", e)

    # Fall back to today's in-memory data if DB is empty
    if month_tokens == 0:
        today = usage_tracker.get_usage_summary(user_id)
        month_tokens = today["tokens_used"]
        month_cost = today["cost_usd"]
        month_requests = today["requests"]

    # Calculate against monthly limits (daily limit × 30 as monthly budget)
    monthly_token_budget = usage_tracker._limits.max_tokens_per_day * 30
    monthly_cost_budget = usage_tracker._limits.max_cost_per_day_usd * 30

    token_pct = month_tokens / monthly_token_budget if monthly_token_budget > 0 else 0
    cost_pct = month_cost / monthly_cost_budget if monthly_cost_budget > 0 else 0
    usage_pct = max(token_pct, cost_pct)

    alert_level = "normal"
    for threshold, level in _ALERT_THRESHOLDS:
        if usage_pct >= threshold:
            alert_level = level
            break

    return api_success(data={
        "month_tokens": month_tokens,
        "month_cost_usd": round(month_cost, 4),
        "month_requests": month_requests,
        "monthly_token_budget": monthly_token_budget,
        "monthly_cost_budget_usd": monthly_cost_budget,
        "usage_percentage": round(usage_pct * 100, 1),
        "alert_level": alert_level,
        "alert_message": _get_alert_message(alert_level, usage_pct),
    })


def _get_alert_message(level: str, pct: float) -> str | None:
    """Generate a user-facing alert message based on quota level."""
    if level == "exhausted":
        return "本月额度已用尽，请联系管理员升级套餐或等待下月重置。"
    elif level == "critical":
        return f"本月额度已使用 {round(pct * 100, 1)}%，即将用尽，请注意控制用量。"
    elif level == "warning":
        return f"本月额度已使用 {round(pct * 100, 1)}%，建议关注用量趋势。"
    return None
