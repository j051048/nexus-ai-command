"""Agent metrics API endpoint."""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from app.core.agent_metrics import get_metrics
from app.core.auth import get_current_user_id
from app.core.config import settings
from app.core.errors import api_success
from app.core.metrics import get_web_vitals_snapshot, observe_web_vital

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/metrics", tags=["Metrics"])

_ALLOWED_WEB_VITALS = {"CLS", "FCP", "INP", "LCP", "TTFB"}
_ALLOWED_WEB_VITAL_RATINGS = {"good", "needs-improvement", "poor", "unknown"}


class WebVitalPayload(BaseModel):
    name: str = Field(..., max_length=24)
    value: float = Field(..., ge=0)
    rating: str = Field(default="unknown", max_length=16)
    id: str | None = Field(default=None, max_length=128)
    path: str = Field(default="/", max_length=256)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in _ALLOWED_WEB_VITALS:
            raise ValueError("unsupported web vital metric")
        return normalized

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, value: str) -> str:
        normalized = (value or "unknown").lower()
        if normalized not in _ALLOWED_WEB_VITAL_RATINGS:
            raise ValueError("unsupported web vital rating")
        return normalized

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        if not value or not value.startswith("/"):
            return "/"
        return value.split("?", 1)[0].split("#", 1)[0] or "/"


@router.get("")
async def get_agent_metrics(user_id: str = Depends(get_current_user_id)):
    """Get Agent execution metrics."""
    metrics = get_metrics()
    return api_success(data=metrics)


@router.post("/web-vitals")
async def record_web_vital(payload: WebVitalPayload):
    """Record frontend Core Web Vitals into Prometheus/in-memory metrics."""
    observe_web_vital(
        name=payload.name,
        value=payload.value,
        rating=payload.rating,
        path=payload.path,
    )
    return api_success(data={"recorded": True})


@router.get("/slo")
async def get_slo_dashboard(user_id: str = Depends(get_current_user_id)):
    """Return a compact SLO dashboard payload for admin/operator pages."""
    metrics = get_metrics()
    total = int(metrics.get("total_requests") or 0)
    errors = int(metrics.get("error_count") or 0)
    success_rate = 1.0 if total == 0 else max(0.0, (total - errors) / total)
    return api_success(
        data={
            "targets": {
                "ai_response_p95_ms": settings.SLO_AI_RESPONSE_P95_MS,
                "api_response_p99_ms": settings.SLO_API_RESPONSE_P99_MS,
                "availability_target": settings.SLO_AVAILABILITY_TARGET,
                "error_budget_window_days": settings.SLO_ERROR_BUDGET_WINDOW_DAYS,
            },
            "agent": {
                "total_requests": total,
                "error_count": errors,
                "success_rate": success_rate,
                "avg_response_time_ms": round(
                    float(metrics.get("avg_response_time") or 0) * 1000,
                    2,
                ),
                "total_tokens": metrics.get("total_tokens", 0),
                "total_cost": metrics.get("total_cost", 0.0),
            },
            "web_vitals": get_web_vitals_snapshot(),
        }
    )
