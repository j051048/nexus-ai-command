from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.models.schemas import PerformanceEvent, StandardResponse
from app.services.performance_service import PerformanceService

router = APIRouter(prefix="/api/performance", tags=["Performance"])


@router.post("/calculate", response_model=StandardResponse)
async def calculate_performance(event: PerformanceEvent, user_id: str = Depends(get_current_user_id)):
    """
    Real-time performance calculation API.

    Accepts performance events (call finished, email sent), calculates score updates,
    and returns immediate feedback including triggered incentives.
    """
    try:
        # P4 Enhancement: Use PerformanceService
        result = await PerformanceService.calculate_and_save(event)

        return api_success(data=result, message="Performance Calculated Successfully")

    except Exception:
        # Catch unexpected errors handled by service layer
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "绩效数据操作失败")


@router.get("/quality-trend", response_model=StandardResponse)
async def quality_trend(
    days: int = Query(7, ge=1, le=90),
    scene_code: str | None = Query(None),
    complexity: str | None = Query(None),
    user_id: str = Depends(get_current_user_id),
):
    """Agent quality scores trend aggregated by day."""
    try:
        from app.core.database import supabase

        since = datetime.now(UTC) - timedelta(days=days)
        query = (
            supabase.table("agent_quality_scores")
            .select("created_at, quality_score, completeness, relevance, accuracy, passed")
            .gte("created_at", since.isoformat())
        )
        if scene_code:
            query = query.eq("scene_code", scene_code)
        if complexity:
            query = query.eq("complexity", complexity)

        res = await query.order("created_at").limit(1000).execute()
        rows = res.data or []

        # Aggregate by day
        daily: dict[str, dict] = defaultdict(
            lambda: {
                "quality_scores": [],
                "completeness": [],
                "relevance": [],
                "accuracy": [],
                "passed": 0,
                "total": 0,
            }
        )
        for row in rows:
            day_key = row["created_at"][:10]  # YYYY-MM-DD
            d = daily[day_key]
            d["quality_scores"].append(row.get("quality_score") or 0)
            d["completeness"].append(row.get("completeness") or 0)
            d["relevance"].append(row.get("relevance") or 0)
            d["accuracy"].append(row.get("accuracy") or 0)
            d["passed"] += 1 if row.get("passed") else 0
            d["total"] += 1

        trend = []
        for day_key in sorted(daily.keys()):
            d = daily[day_key]
            n = d["total"]
            trend.append(
                {
                    "date": day_key,
                    "avg_quality_score": round(sum(d["quality_scores"]) / n, 3),
                    "avg_completeness": round(sum(d["completeness"]) / n, 3),
                    "avg_relevance": round(sum(d["relevance"]) / n, 3),
                    "avg_accuracy": round(sum(d["accuracy"]) / n, 3),
                    "pass_rate": round(d["passed"] / n, 3),
                    "total_evaluations": n,
                }
            )

        return api_success(data={"days": days, "trend": trend})
    except Exception:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "绩效数据操作失败")
