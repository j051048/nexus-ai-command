"""
Tenant Metering Service.

Records per-call LLM / Tool / RAG usage, provides aggregation,
quota checking, and invoice data export.

Uses Redis for real-time atomic counters with periodic flush to
Supabase ``tenant_usage_records`` table.  Gracefully degrades when
Redis or database are not available.
"""

import logging
import os
import time
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default per-model cost table (USD per 1K tokens)
# Override via MODEL_PRICING env var (JSON) if needed
# ---------------------------------------------------------------------------
DEFAULT_MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "deepseek-chat": {"input": 0.0014, "output": 0.0028},
}

# Default quotas per tier (monthly)
DEFAULT_TIER_QUOTAS: dict[str, dict[str, int]] = {
    "free": {"llm_calls": 100, "tool_calls": 500, "rag_queries": 200},
    "basic": {"llm_calls": 5_000, "tool_calls": 20_000, "rag_queries": 10_000},
    "premium": {"llm_calls": 50_000, "tool_calls": 200_000, "rag_queries": 100_000},
    "enterprise": {"llm_calls": -1, "tool_calls": -1, "rag_queries": -1},  # unlimited
}

# Redis key prefixes
_REDIS_PREFIX = "metering"


def _redis_key(tenant_id: str, resource: str, month: str) -> str:
    return f"{_REDIS_PREFIX}:{tenant_id}:{resource}:{month}"


def _current_month() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


# ---------------------------------------------------------------------------
# Redis helper
# ---------------------------------------------------------------------------
_redis_client = None
_redis_checked = False


async def _get_redis():
    """Return an async Redis client or None."""
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    redis_url = os.getenv("REDIS_URL", "")
    if not redis_url:
        return None
    try:
        import redis.asyncio as aioredis
        _redis_client = aioredis.from_url(redis_url, decode_responses=True)
        await _redis_client.ping()
        return _redis_client
    except Exception as exc:
        logger.warning("Redis unavailable for metering: %s", exc)
        _redis_client = None
        return None


# ---------------------------------------------------------------------------
# TenantMeteringService
# ---------------------------------------------------------------------------
class TenantMeteringService:
    """Usage metering with Redis counters + Supabase persistence."""

    def __init__(self, model_pricing: dict | None = None, tier_quotas: dict | None = None):
        self._pricing = model_pricing or DEFAULT_MODEL_PRICING
        self._quotas = tier_quotas or DEFAULT_TIER_QUOTAS

    @staticmethod
    def _get_db():
        from app.core.database import supabase
        return supabase

    # -----------------------------------------------------------------------
    # Recording
    # -----------------------------------------------------------------------
    async def record_llm_usage(
        self,
        tenant_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float | None = None,
    ) -> None:
        """Record a single LLM call.

        If cost_usd is not provided, it is estimated from the model pricing table.
        """
        if cost_usd is None:
            pricing = self._pricing.get(model, self._pricing.get("gpt-4o-mini", {}))
            cost_usd = (
                input_tokens / 1000 * pricing.get("input", 0)
                + output_tokens / 1000 * pricing.get("output", 0)
            )

        record = {
            "tenant_id": tenant_id,
            "record_type": "llm",
            "model_name": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost_usd, 6),
            "metadata": {},
        }
        await self._persist_record(record)
        await self._incr_redis_counter(tenant_id, "llm_calls", 1)

    async def record_tool_usage(
        self,
        tenant_id: str,
        tool_name: str,
        execution_time_ms: int,
    ) -> None:
        """Record a tool invocation."""
        record = {
            "tenant_id": tenant_id,
            "record_type": "tool",
            "tool_name": tool_name,
            "execution_time_ms": execution_time_ms,
            "metadata": {},
        }
        await self._persist_record(record)
        await self._incr_redis_counter(tenant_id, "tool_calls", 1)

    async def record_rag_usage(
        self,
        tenant_id: str,
        query_count: int,
        chunks_retrieved: int,
    ) -> None:
        """Record RAG retrieval operations."""
        record = {
            "tenant_id": tenant_id,
            "record_type": "rag",
            "metadata": {"query_count": query_count, "chunks_retrieved": chunks_retrieved},
        }
        await self._persist_record(record)
        await self._incr_redis_counter(tenant_id, "rag_queries", query_count)

    # -----------------------------------------------------------------------
    # Querying
    # -----------------------------------------------------------------------
    async def get_usage_summary(
        self, tenant_id: str, period: str = "current_month"
    ) -> dict[str, Any]:
        """Aggregated usage stats for a tenant.

        ``period`` can be ``current_month`` or a ``YYYY-MM`` string.
        """
        month = _current_month() if period == "current_month" else period
        start, end = self._month_range(month)

        db = self._get_db()
        if not db:
            return self._empty_summary(month)

        try:
            resp = await (
                db.table("tenant_usage_records")
                .select("record_type, input_tokens, output_tokens, cost_usd, execution_time_ms")
                .eq("tenant_id", tenant_id)
                .gte("created_at", start)
                .lt("created_at", end)
                .execute()
            )
            rows = resp.data if resp else []
        except Exception as exc:
            logger.warning("get_usage_summary query failed: %s", exc)
            rows = []

        summary: dict[str, Any] = {
            "month": month,
            "llm": {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
            "tool": {"calls": 0, "avg_execution_time_ms": 0.0},
            "rag": {"calls": 0},
            "total_cost_usd": 0.0,
        }
        tool_times: list[int] = []
        for r in rows:
            rt = r.get("record_type", "")
            if rt == "llm":
                summary["llm"]["calls"] += 1
                summary["llm"]["input_tokens"] += r.get("input_tokens", 0) or 0
                summary["llm"]["output_tokens"] += r.get("output_tokens", 0) or 0
                summary["llm"]["cost_usd"] += float(r.get("cost_usd", 0) or 0)
            elif rt == "tool":
                summary["tool"]["calls"] += 1
                t = r.get("execution_time_ms", 0) or 0
                if t:
                    tool_times.append(t)
            elif rt == "rag":
                summary["rag"]["calls"] += 1
            summary["total_cost_usd"] += float(r.get("cost_usd", 0) or 0)

        if tool_times:
            summary["tool"]["avg_execution_time_ms"] = round(sum(tool_times) / len(tool_times), 1)
        summary["total_cost_usd"] = round(summary["total_cost_usd"], 6)
        summary["llm"]["cost_usd"] = round(summary["llm"]["cost_usd"], 6)
        return summary

    async def get_cost_breakdown(
        self, tenant_id: str, period: str = "current_month"
    ) -> dict[str, Any]:
        """Cost breakdown by model/tool/category."""
        month = _current_month() if period == "current_month" else period
        start, end = self._month_range(month)

        db = self._get_db()
        if not db:
            return {"month": month, "by_model": {}, "by_type": {}, "total_cost_usd": 0.0}

        try:
            resp = await (
                db.table("tenant_usage_records")
                .select("record_type, model_name, tool_name, cost_usd")
                .eq("tenant_id", tenant_id)
                .gte("created_at", start)
                .lt("created_at", end)
                .execute()
            )
            rows = resp.data if resp else []
        except Exception as exc:
            logger.warning("get_cost_breakdown query failed: %s", exc)
            rows = []

        by_model: dict[str, float] = {}
        by_type: dict[str, float] = {}
        total = 0.0

        for r in rows:
            cost = float(r.get("cost_usd", 0) or 0)
            total += cost
            rt = r.get("record_type", "other")
            by_type[rt] = by_type.get(rt, 0.0) + cost
            model = r.get("model_name") or r.get("tool_name") or "unknown"
            by_model[model] = by_model.get(model, 0.0) + cost

        return {
            "month": month,
            "by_model": {k: round(v, 6) for k, v in by_model.items()},
            "by_type": {k: round(v, 6) for k, v in by_type.items()},
            "total_cost_usd": round(total, 6),
        }

    async def check_quota(
        self, tenant_id: str, resource_type: str
    ) -> dict[str, Any]:
        """Check whether tenant has remaining quota for a resource type.

        ``resource_type``: ``llm_calls``, ``tool_calls``, ``rag_queries``

        Returns {"allowed": bool, "used": int, "limit": int, "remaining": int}.
        """
        month = _current_month()

        # Get tenant tier
        tier = await self._get_tenant_tier(tenant_id)
        quotas = self._quotas.get(tier, self._quotas.get("free", {}))
        limit = quotas.get(resource_type, 0)

        # -1 means unlimited
        if limit == -1:
            return {"allowed": True, "used": 0, "limit": -1, "remaining": -1}

        # Try Redis first for fast counter
        used = await self._get_redis_counter(tenant_id, resource_type, month)

        # Fallback to DB count
        if used is None:
            used = await self._count_from_db(tenant_id, resource_type, month)

        remaining = max(0, limit - used)
        return {
            "allowed": used < limit,
            "used": used,
            "limit": limit,
            "remaining": remaining,
        }

    async def export_invoice_data(
        self, tenant_id: str, month: str
    ) -> dict[str, Any]:
        """Export usage data suitable for invoice generation."""
        summary = await self.get_usage_summary(tenant_id, period=month)
        breakdown = await self.get_cost_breakdown(tenant_id, period=month)
        return {
            "tenant_id": tenant_id,
            "billing_period": month,
            "summary": summary,
            "cost_breakdown": breakdown,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------
    async def _persist_record(self, record: dict) -> None:
        """Insert a usage record into Supabase."""
        db = self._get_db()
        if not db:
            logger.debug("Metering: DB not available, record dropped: %s", record.get("record_type"))
            return
        try:
            await db.table("tenant_usage_records").insert(record).execute()
        except Exception as exc:
            logger.warning("Failed to persist usage record: %s", exc)

    async def _incr_redis_counter(self, tenant_id: str, resource: str, amount: int) -> None:
        """Atomically increment a Redis counter for fast quota checks."""
        r = await _get_redis()
        if not r:
            return
        key = _redis_key(tenant_id, resource, _current_month())
        try:
            await r.incrby(key, amount)
            # Auto-expire at end of month + 1 day buffer
            await r.expire(key, 32 * 86400)
        except Exception as exc:
            logger.debug("Redis INCRBY failed: %s", exc)

    async def _get_redis_counter(self, tenant_id: str, resource: str, month: str) -> int | None:
        """Read current counter from Redis. Returns None if unavailable."""
        r = await _get_redis()
        if not r:
            return None
        try:
            val = await r.get(_redis_key(tenant_id, resource, month))
            return int(val) if val is not None else 0
        except Exception:
            return None

    async def _count_from_db(self, tenant_id: str, resource_type: str, month: str) -> int:
        """Count usage records from database as fallback."""
        db = self._get_db()
        if not db:
            return 0
        start, end = self._month_range(month)
        # Map resource_type to record_type
        type_map = {"llm_calls": "llm", "tool_calls": "tool", "rag_queries": "rag"}
        record_type = type_map.get(resource_type, resource_type)
        try:
            resp = await (
                db.table("tenant_usage_records")
                .select("id", count="exact")
                .eq("tenant_id", tenant_id)
                .eq("record_type", record_type)
                .gte("created_at", start)
                .lt("created_at", end)
                .execute()
            )
            return resp.count if hasattr(resp, "count") and resp.count else len(resp.data or [])
        except Exception as exc:
            logger.warning("_count_from_db failed: %s", exc)
            return 0

    async def _get_tenant_tier(self, tenant_id: str) -> str:
        """Look up tenant tier from DB, default to 'free'."""
        db = self._get_db()
        if not db:
            return "free"
        try:
            resp = await (
                db.table("tenants")
                .select("tier")
                .eq("id", tenant_id)
                .limit(1)
                .execute()
            )
            rows = resp.data if resp else []
            return rows[0].get("tier", "free") if rows else "free"
        except Exception:
            return "free"

    @staticmethod
    def _month_range(month: str) -> tuple[str, str]:
        """Return (start_iso, end_iso) for a YYYY-MM month."""
        dt = datetime.strptime(month, "%Y-%m").replace(tzinfo=UTC)
        # Next month
        if dt.month == 12:
            next_dt = dt.replace(year=dt.year + 1, month=1)
        else:
            next_dt = dt.replace(month=dt.month + 1)
        return dt.isoformat(), next_dt.isoformat()

    @staticmethod
    def _empty_summary(month: str) -> dict[str, Any]:
        return {
            "month": month,
            "llm": {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
            "tool": {"calls": 0, "avg_execution_time_ms": 0.0},
            "rag": {"calls": 0},
            "total_cost_usd": 0.0,
        }


# Singleton
tenant_metering = TenantMeteringService()
