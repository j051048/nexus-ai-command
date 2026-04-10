"""
AI Quality Metrics Service - Aggregates and persists quality metrics daily.
Provides data for the quality dashboard.
"""

import logging
from datetime import UTC, datetime, timedelta

from app.core.database import supabase

logger = logging.getLogger(__name__)


class AIQualityService:
    """Aggregates agent execution quality metrics."""

    async def aggregate_daily_metrics(
        self, tenant_id: str | None = None, db=None
    ) -> dict:
        """
        Aggregate today's metrics from agent_trace_service and persist to ai_quality_daily.
        Called by Celery beat task daily.
        """
        db = db or supabase
        if not db:
            return {"status": "skipped", "reason": "no db"}

        from app.services.agent_trace_service import agent_trace_service

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        stats = agent_trace_service.get_stats(org_id=tenant_id)

        if stats.get("total_traces", 0) == 0:
            return {"status": "skipped", "reason": "no traces"}

        # Get feedback counts for today
        positive = 0
        negative = 0
        try:
            today_start = (
                datetime.now(UTC).replace(hour=0, minute=0, second=0).isoformat()
            )
            fb_query = db.table("ai_feedback").select("rating", count="exact")
            if tenant_id:
                fb_query = fb_query.eq("tenant_id", tenant_id)
            fb_query = fb_query.gte("created_at", today_start)

            pos_res = await fb_query.eq("rating", "positive").execute()
            positive = pos_res.count if pos_res.count else 0

            neg_query = db.table("ai_feedback").select("rating", count="exact")
            if tenant_id:
                neg_query = neg_query.eq("tenant_id", tenant_id)
            neg_query = neg_query.gte("created_at", today_start)
            neg_res = await neg_query.eq("rating", "negative").execute()
            negative = neg_res.count if neg_res.count else 0
        except Exception as e:
            logger.error("Feedback count failed: %s", e)

        by_status = stats.get("by_status", {})
        record = {
            "tenant_id": tenant_id,
            "metric_date": today,
            "total_traces": stats.get("total_traces", 0),
            "completed_traces": by_status.get("completed", 0),
            "failed_traces": by_status.get("failed", 0),
            "timeout_traces": by_status.get("timeout", 0),
            "total_tokens": stats.get("total_tokens", 0),
            "total_cost_usd": round(stats.get("total_cost_usd", 0), 4),
            "avg_duration_ms": int(stats.get("avg_duration_ms", 0)),
            "positive_feedback": positive,
            "negative_feedback": negative,
        }

        try:
            await db.table("ai_quality_daily").upsert(
                record, on_conflict="tenant_id,metric_date"
            ).execute()
            logger.info(
                "AI quality metrics aggregated for %s: %s", tenant_id or "global", today
            )
            return {"status": "ok", "date": today, "metrics": record}
        except Exception as e:
            logger.error("Failed to persist AI quality metrics: %s", e)
            return {"status": "error", "reason": str(e)}

    async def get_quality_trend(
        self,
        tenant_id: str | None = None,
        days: int = 30,
        db=None,
    ) -> list[dict]:
        """Get daily quality metrics for the last N days."""
        db = db or supabase
        if not db:
            return []

        try:
            since = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
            query = (
                db.table("ai_quality_daily")
                .select("*")
                .gte("metric_date", since)
                .order("metric_date", desc=False)
            )
            if tenant_id:
                query = query.eq("tenant_id", tenant_id)

            res = await query.execute()
            return res.data or []
        except Exception as e:
            logger.error("Failed to get quality trend: %s", e)
            return []

    async def get_quality_summary(
        self,
        tenant_id: str | None = None,
        days: int = 7,
        db=None,
    ) -> dict:
        """Get aggregated quality summary for dashboard cards."""
        trend = await self.get_quality_trend(tenant_id, days, db)
        if not trend:
            return {
                "total_traces": 0,
                "success_rate": 0,
                "avg_duration_ms": 0,
                "total_tokens": 0,
                "total_cost_usd": 0,
                "satisfaction_rate": 0,
                "days": days,
            }

        total_traces = sum(d.get("total_traces", 0) for d in trend)
        completed = sum(d.get("completed_traces", 0) for d in trend)
        total_tokens = sum(d.get("total_tokens", 0) for d in trend)
        total_cost = sum(float(d.get("total_cost_usd", 0)) for d in trend)
        durations = [
            d.get("avg_duration_ms", 0) for d in trend if d.get("avg_duration_ms")
        ]
        pos = sum(d.get("positive_feedback", 0) for d in trend)
        neg = sum(d.get("negative_feedback", 0) for d in trend)

        return {
            "total_traces": total_traces,
            "success_rate": (
                round(completed / total_traces * 100, 1) if total_traces else 0
            ),
            "avg_duration_ms": int(sum(durations) / len(durations)) if durations else 0,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "satisfaction_rate": (
                round(pos / (pos + neg) * 100, 1) if (pos + neg) > 0 else 0
            ),
            "positive_feedback": pos,
            "negative_feedback": neg,
            "days": days,
        }


ai_quality_service = AIQualityService()
