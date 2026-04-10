"""
LLM Model Adaptation Gateway - Quota Management Service

Manages per-tenant/per-model/per-user usage quotas.
Features:
- Check quota before making LLM calls
- Record usage after calls complete
- In-memory caching with 5-minute TTL for quota configs
- Warning at 80% threshold
- Block or allow overage based on quota config
"""

import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class QuotaConfig:
    """Quota configuration for a tenant + model combination."""

    tenant_id: str
    model_code: str | None  # None = tenant-wide quota
    user_id: str | None  # None = applies to all users
    period: str  # daily / monthly
    max_tokens: int
    max_cost: float  # USD
    max_requests: int
    overage_action: str  # block / warn / allow
    loaded_at: float = 0.0  # Timestamp when loaded from DB


@dataclass
class QuotaCheckResult:
    """Result of a quota check."""

    allowed: bool
    reason: str
    warning: bool = False
    usage_pct: float = 0.0  # Current usage percentage


# In-memory quota config cache: key -> (config_list, loaded_at)
_quota_cache: dict[str, tuple[list[QuotaConfig], float]] = {}
_CACHE_TTL = 300  # 5 minutes

# In-memory usage accumulator: key -> {tokens, cost, requests}
_usage_cache: dict[str, dict] = {}


def _cache_key(
    tenant_id: str, model_code: str | None = None, user_id: str | None = None
) -> str:
    """Build a cache key for quota lookup."""
    parts = [tenant_id]
    if model_code:
        parts.append(model_code)
    if user_id:
        parts.append(user_id)
    return ":".join(parts)


def _usage_key(tenant_id: str, model_code: str, period: str) -> str:
    """Build a usage accumulator key."""
    date_part = (
        time.strftime("%Y-%m-%d") if period == "daily" else time.strftime("%Y-%m")
    )
    return f"usage:{tenant_id}:{model_code}:{date_part}"


async def _load_quota_configs(tenant_id: str) -> list[QuotaConfig]:
    """
    Load quota configs from the llm_quota_config table.
    Caches results for _CACHE_TTL seconds.
    """
    cache_k = f"configs:{tenant_id}"
    now = time.time()

    if cache_k in _quota_cache:
        configs, loaded_at = _quota_cache[cache_k]
        if now - loaded_at < _CACHE_TTL:
            return configs

    configs: list[QuotaConfig] = []
    try:
        from app.core.database import supabase

        if not supabase:
            return configs

        res = (
            await supabase.table("llm_quota_config")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("is_active", True)
            .execute()
        )

        for row in res.data or []:
            configs.append(
                QuotaConfig(
                    tenant_id=row.get("tenant_id", tenant_id),
                    model_code=row.get("model_code"),
                    user_id=row.get("user_id"),
                    period=row.get("period", "daily"),
                    max_tokens=row.get("max_tokens", 0),
                    max_cost=float(row.get("max_cost", 0.0)),
                    max_requests=row.get("max_requests", 0),
                    overage_action=row.get("overage_action", "warn"),
                    loaded_at=now,
                )
            )

    except Exception as e:
        logger.warning(f"Failed to load quota configs for tenant {tenant_id}: {e}")

    _quota_cache[cache_k] = (configs, now)
    return configs


async def _load_usage_from_db(tenant_id: str, model_code: str, period: str) -> dict:
    """
    Load current period usage from llm_usage_stats table.
    Falls back to in-memory accumulator if DB is unavailable.
    """
    u_key = _usage_key(tenant_id, model_code, period)

    # Check in-memory first
    if u_key in _usage_cache:
        return _usage_cache[u_key]

    usage = {"tokens": 0, "cost": 0.0, "requests": 0}

    try:
        from app.core.database import supabase

        if not supabase:
            _usage_cache[u_key] = usage
            return usage

        date_filter = (
            time.strftime("%Y-%m-%d")
            if period == "daily"
            else time.strftime("%Y-%m-01")
        )

        query = (
            supabase.table("llm_usage_stats")
            .select("total_tokens, total_cost, total_requests")
            .eq("tenant_id", tenant_id)
        )

        if model_code != "__all__":
            query = query.eq("model_code", model_code)

        query = (
            query.eq("stat_date", date_filter)
            if period == "daily"
            else query.gte("stat_date", date_filter)
        )

        res = await query.execute()

        for row in res.data or []:
            usage["tokens"] += row.get("total_tokens", 0)
            usage["cost"] += float(row.get("total_cost", 0.0))
            usage["requests"] += row.get("total_requests", 0)

    except Exception as e:
        logger.warning(
            f"Failed to load usage from DB for {tenant_id}/{model_code}: {e}"
        )

    _usage_cache[u_key] = usage
    return usage


async def check_quota(
    tenant_id: str,
    model_code: str,
    user_id: str,
    estimated_tokens: int = 0,
) -> QuotaCheckResult:
    """
    Check if the request is within quota limits.

    Checks are performed in order:
    1. User-specific quota for this model
    2. Model-specific tenant quota
    3. Tenant-wide quota

    Returns QuotaCheckResult with allowed=True/False and reason.
    """
    configs = await _load_quota_configs(tenant_id)

    if not configs:
        # No quota configured = no restrictions
        return QuotaCheckResult(allowed=True, reason="No quota configured")

    # Sort configs by specificity: user+model > model > tenant-wide
    def specificity(cfg: QuotaConfig) -> int:
        score = 0
        if cfg.model_code:
            score += 1
        if cfg.user_id:
            score += 2
        return score

    configs.sort(key=specificity, reverse=True)

    for cfg in configs:
        # Skip configs that don't match
        if cfg.model_code and cfg.model_code != model_code:
            continue
        if cfg.user_id and cfg.user_id != user_id:
            continue

        # Load usage for this scope
        scope_model = cfg.model_code or "__all__"
        usage = await _load_usage_from_db(tenant_id, scope_model, cfg.period)

        # Check token quota
        if cfg.max_tokens > 0:
            projected_tokens = usage["tokens"] + estimated_tokens
            token_pct = usage["tokens"] / cfg.max_tokens if cfg.max_tokens > 0 else 0.0

            if projected_tokens > cfg.max_tokens:
                if cfg.overage_action == "block":
                    return QuotaCheckResult(
                        allowed=False,
                        reason=(
                            f"Token quota exceeded for {cfg.period} period: "
                            f"{usage['tokens']}/{cfg.max_tokens} used, "
                            f"estimated {estimated_tokens} needed"
                        ),
                        usage_pct=token_pct,
                    )
                elif cfg.overage_action == "warn":
                    return QuotaCheckResult(
                        allowed=True,
                        reason=f"Token quota will be exceeded ({usage['tokens']}/{cfg.max_tokens})",
                        warning=True,
                        usage_pct=token_pct,
                    )

            # 80% warning threshold
            if token_pct >= 0.8 and token_pct < 1.0:
                return QuotaCheckResult(
                    allowed=True,
                    reason=f"Approaching token quota limit: {token_pct:.0%} used",
                    warning=True,
                    usage_pct=token_pct,
                )

        # Check cost quota
        if cfg.max_cost > 0:
            cost_pct = usage["cost"] / cfg.max_cost if cfg.max_cost > 0 else 0.0
            if usage["cost"] >= cfg.max_cost:
                if cfg.overage_action == "block":
                    return QuotaCheckResult(
                        allowed=False,
                        reason=(
                            f"Cost quota exceeded for {cfg.period} period: ${usage['cost']:.4f}/${cfg.max_cost:.2f}"
                        ),
                        usage_pct=cost_pct,
                    )
                elif cfg.overage_action == "warn":
                    return QuotaCheckResult(
                        allowed=True,
                        reason=f"Cost quota exceeded (${usage['cost']:.4f}/${cfg.max_cost:.2f})",
                        warning=True,
                        usage_pct=cost_pct,
                    )

            if cost_pct >= 0.8 and cost_pct < 1.0:
                return QuotaCheckResult(
                    allowed=True,
                    reason=f"Approaching cost quota limit: {cost_pct:.0%} used",
                    warning=True,
                    usage_pct=cost_pct,
                )

        # Check request count quota
        if cfg.max_requests > 0:
            req_pct = (
                usage["requests"] / cfg.max_requests if cfg.max_requests > 0 else 0.0
            )
            if usage["requests"] >= cfg.max_requests:
                if cfg.overage_action == "block":
                    return QuotaCheckResult(
                        allowed=False,
                        reason=(
                            f"Request quota exceeded for {cfg.period} period: {usage['requests']}/{cfg.max_requests}"
                        ),
                        usage_pct=req_pct,
                    )
                elif cfg.overage_action == "warn":
                    return QuotaCheckResult(
                        allowed=True,
                        reason=f"Request quota exceeded ({usage['requests']}/{cfg.max_requests})",
                        warning=True,
                        usage_pct=req_pct,
                    )

            if req_pct >= 0.8 and req_pct < 1.0:
                return QuotaCheckResult(
                    allowed=True,
                    reason=f"Approaching request quota limit: {req_pct:.0%} used",
                    warning=True,
                    usage_pct=req_pct,
                )

    return QuotaCheckResult(allowed=True, reason="Within quota limits")


async def record_usage(
    tenant_id: str,
    model_code: str,
    user_id: str,
    tokens: int,
    cost: float,
):
    """
    Record usage after a completed LLM call.
    Updates both in-memory cache and persists to database.
    """
    # Update in-memory accumulators for all relevant periods
    for period in ("daily", "monthly"):
        for scope_model in (model_code, "__all__"):
            u_key = _usage_key(tenant_id, scope_model, period)
            if u_key not in _usage_cache:
                _usage_cache[u_key] = {"tokens": 0, "cost": 0.0, "requests": 0}
            _usage_cache[u_key]["tokens"] += tokens
            _usage_cache[u_key]["cost"] += cost
            _usage_cache[u_key]["requests"] += 1

    # Persist to database
    try:
        from app.core.database import supabase

        if not supabase:
            return

        stat_date = time.strftime("%Y-%m-%d")
        await supabase.rpc(
            "upsert_llm_usage_stats",
            {
                "p_tenant_id": tenant_id,
                "p_model_code": model_code,
                "p_user_id": user_id,
                "p_stat_date": stat_date,
                "p_tokens": tokens,
                "p_cost": cost,
            },
        ).execute()

    except Exception as e:
        logger.warning(f"Failed to persist LLM usage to DB: {e}")
        # Non-fatal: in-memory tracking still works


def invalidate_cache(tenant_id: str | None = None):
    """
    Invalidate quota config cache.
    If tenant_id is None, invalidate all caches.
    """
    global _quota_cache, _usage_cache

    if tenant_id is None:
        _quota_cache.clear()
        _usage_cache.clear()
        logger.info("All quota caches invalidated")
    else:
        keys_to_remove = [k for k in _quota_cache if tenant_id in k]
        for k in keys_to_remove:
            del _quota_cache[k]

        usage_keys_to_remove = [k for k in _usage_cache if tenant_id in k]
        for k in usage_keys_to_remove:
            del _usage_cache[k]

        logger.info(f"Quota cache invalidated for tenant {tenant_id}")


def get_quota_stats(tenant_id: str) -> dict:
    """Get current quota usage statistics for a tenant."""
    stats = {
        "tenant_id": tenant_id,
        "cached_configs": 0,
        "cached_usage_entries": 0,
        "usage_by_model": {},
    }

    cache_k = f"configs:{tenant_id}"
    if cache_k in _quota_cache:
        configs, _ = _quota_cache[cache_k]
        stats["cached_configs"] = len(configs)

    for k, v in _usage_cache.items():
        if tenant_id in k:
            stats["cached_usage_entries"] += 1
            # Extract model from key
            parts = k.split(":")
            if len(parts) >= 3:
                model = parts[2]
                stats["usage_by_model"][model] = v

    return stats
