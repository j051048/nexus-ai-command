"""
G5: Token 燃烧秒级熔断 — 单会话成本上限

防止死循环长对话无限消耗 token，通过多维度预算控制：
- 单次会话最大 token 数
- 单用户每小时 token 上限
- 单次会话最大费用
- 单租户每日费用上限

使用 Redis 原子计数器（可用时），否则 in-memory fallback。
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import StrEnum

from app.core.config import settings
from app.core.model_pricing import (
    estimate_cost,
)  # noqa: F401 — re-exported for backwards compat

logger = logging.getLogger(__name__)


# ─── Budget Status ─────────────────────────────────────────────────────────


class BudgetVerdict(StrEnum):
    OK = "ok"
    WARNING = "warning"  # > 80% of budget
    EXCEEDED = "exceeded"


@dataclass
class BudgetStatus:
    verdict: BudgetVerdict
    message: str = ""
    session_tokens: int = 0
    session_cost_usd: float = 0.0
    user_hour_tokens: int = 0
    tenant_day_cost_usd: float = 0.0
    tenant_month_cost_usd: float = 0.0


@dataclass
class UsageSummary:
    session_input_tokens: int = 0
    session_output_tokens: int = 0
    session_total_tokens: int = 0
    session_cost_usd: float = 0.0
    user_hour_tokens: int = 0
    tenant_day_cost_usd: float = 0.0
    tenant_month_cost_usd: float = 0.0


# ─── In-Memory Fallback Store ──────────────────────────────────────────────


class _InMemoryBudgetStore:
    """Thread-safe in-memory counters with automatic expiry."""

    def __init__(self):
        self._data: dict[str, tuple[int | float, float]] = (
            {}
        )  # key -> (value, expires_at)
        self._lock = asyncio.Lock()

    async def incr_by(self, key: str, amount: int | float, ttl: int) -> float:
        async with self._lock:
            now = time.time()
            current, expires = self._data.get(key, (0, 0))
            if expires and now > expires:
                current = 0
                expires = now + ttl
            elif not expires:
                expires = now + ttl
            new_val = current + amount
            self._data[key] = (new_val, expires)
            return new_val

    async def get_val(self, key: str) -> float:
        async with self._lock:
            now = time.time()
            val, expires = self._data.get(key, (0, 0))
            if expires and now > expires:
                return 0
            return val


# ─── Token Budget Manager ─────────────────────────────────────────────────


class TokenBudgetManager:
    """
    Multi-dimensional token budget enforcement.

    Checks and records token/cost usage across:
    - Per-session token limit
    - Per-user hourly token limit
    - Per-session cost limit (USD)
    - Per-tenant daily cost limit (USD)
    """

    def __init__(self):
        self._memory_store = _InMemoryBudgetStore()
        self._redis_client = None

    async def _get_redis(self):
        """Lazily get Redis client from cache_service."""
        if self._redis_client is not None:
            return self._redis_client
        try:
            from app.services.cache_service import cache_service

            if cache_service._use_redis and cache_service._client:
                self._redis_client = cache_service._client
                return self._redis_client
        except Exception as e:
            logger.warning("[TokenBudget] Redis client init failed, using memory fallback: %s", e)

    def _key(self, dimension: str, entity_id: str) -> str:
        return f"tkbudget:{dimension}:{entity_id}"

    async def _incr(self, key: str, amount: float, ttl: int) -> float:
        """Atomic increment with TTL. Uses Redis if available, else in-memory."""
        redis = await self._get_redis()
        if redis:
            try:
                pipe = redis.pipeline()
                if isinstance(amount, float):
                    # Use INCRBYFLOAT for cost
                    pipe.incrbyfloat(key, amount)
                else:
                    pipe.incrby(key, int(amount))
                pipe.expire(key, ttl)
                results = await pipe.execute()
                return float(results[0])
            except Exception as e:
                logger.warning(f"[TokenBudget] Redis incr failed, using memory: {e}")
        return await self._memory_store.incr_by(key, amount, ttl)

    async def _get(self, key: str) -> float:
        redis = await self._get_redis()
        if redis:
            try:
                val = await redis.get(key)
                return float(val) if val else 0
            except Exception as e:
                logger.warning("[TokenBudget] Redis get failed for %s: %s", key, e)

    async def check_budget(
        self,
        session_id: str,
        user_id: str,
        tenant_id: str | None = None,
    ) -> BudgetStatus:
        """
        Check whether the current session/user/tenant is within budget.
        Returns EXCEEDED if any limit is breached, WARNING if > 80%.
        """
        # 1. Session token check
        sess_tokens = await self._get(self._key("sess_tok", session_id))
        if sess_tokens >= settings.TOKEN_BUDGET_MAX_PER_SESSION:
            return BudgetStatus(
                verdict=BudgetVerdict.EXCEEDED,
                message=f"本次会话已使用 {int(sess_tokens)} tokens，超过单会话上限 {settings.TOKEN_BUDGET_MAX_PER_SESSION}。请开启新会话继续对话。",
                session_tokens=int(sess_tokens),
            )

        # 2. User hourly token check
        user_hour_key = self._key("user_hr", f"{user_id}:{int(time.time() // 3600)}")
        user_hour_tokens = await self._get(user_hour_key)
        if user_hour_tokens >= settings.TOKEN_BUDGET_MAX_PER_HOUR_PER_USER:
            return BudgetStatus(
                verdict=BudgetVerdict.EXCEEDED,
                message=f"您在过去一小时内已使用 {int(user_hour_tokens)} tokens，超过每小时上限 {settings.TOKEN_BUDGET_MAX_PER_HOUR_PER_USER}。请稍后再试。",
                user_hour_tokens=int(user_hour_tokens),
            )

        # 3. Session cost check
        sess_cost = await self._get(self._key("sess_cost", session_id))
        if sess_cost >= settings.TOKEN_BUDGET_MAX_COST_PER_SESSION:
            return BudgetStatus(
                verdict=BudgetVerdict.EXCEEDED,
                message=f"本次会话费用已达 ${sess_cost:.2f}，超过单会话费用上限 ${settings.TOKEN_BUDGET_MAX_COST_PER_SESSION:.2f}。请开启新会话。",
                session_cost_usd=sess_cost,
            )

        # 4. Tenant daily cost check
        if tenant_id:
            day_key = self._key(
                "tenant_day", f"{tenant_id}:{int(time.time() // 86400)}"
            )
            tenant_cost = await self._get(day_key)
            if tenant_cost >= settings.TOKEN_BUDGET_MAX_COST_PER_DAY_PER_TENANT:
                return BudgetStatus(
                    verdict=BudgetVerdict.EXCEEDED,
                    message=f"您所在组织今日 AI 费用已达 ${tenant_cost:.2f}，超过每日上限 ${settings.TOKEN_BUDGET_MAX_COST_PER_DAY_PER_TENANT:.2f}。请联系管理员。",
                    tenant_day_cost_usd=tenant_cost,
                )

            # 5. Tenant monthly cost check (P0: 防止月度成本失控)
            month_key = self._key(
                "tenant_month", f"{tenant_id}:{time.strftime('%Y-%m')}"
            )
            tenant_month_cost = await self._get(month_key)
            if tenant_month_cost >= settings.TOKEN_BUDGET_MAX_COST_PER_MONTH_PER_TENANT:
                return BudgetStatus(
                    verdict=BudgetVerdict.EXCEEDED,
                    message=f"您所在组织本月 AI 费用已达 ${tenant_month_cost:.2f}，超过月度上限 ${settings.TOKEN_BUDGET_MAX_COST_PER_MONTH_PER_TENANT:.2f}。请下月再试或联系管理员提升额度。",
                    tenant_month_cost_usd=tenant_month_cost,
                )

        # Warning checks (> 80% of any limit)
        warning_threshold = 0.8
        warnings = []
        if sess_tokens >= settings.TOKEN_BUDGET_MAX_PER_SESSION * warning_threshold:
            warnings.append(
                f"会话 token 已使用 {int(sess_tokens)}/{settings.TOKEN_BUDGET_MAX_PER_SESSION}"
            )
        if (
            user_hour_tokens
            >= settings.TOKEN_BUDGET_MAX_PER_HOUR_PER_USER * warning_threshold
        ):
            warnings.append(
                f"小时 token 已使用 {int(user_hour_tokens)}/{settings.TOKEN_BUDGET_MAX_PER_HOUR_PER_USER}"
            )
        if sess_cost >= settings.TOKEN_BUDGET_MAX_COST_PER_SESSION * warning_threshold:
            warnings.append(
                f"会话费用 ${sess_cost:.2f}/${settings.TOKEN_BUDGET_MAX_COST_PER_SESSION:.2f}"
            )

        if warnings:
            return BudgetStatus(
                verdict=BudgetVerdict.WARNING,
                message="接近预算上限: " + "; ".join(warnings),
                session_tokens=int(sess_tokens),
                session_cost_usd=sess_cost,
                user_hour_tokens=int(user_hour_tokens),
            )

        return BudgetStatus(
            verdict=BudgetVerdict.OK,
            session_tokens=int(sess_tokens),
            session_cost_usd=sess_cost,
            user_hour_tokens=int(user_hour_tokens),
        )

    async def record_usage(
        self,
        session_id: str,
        user_id: str,
        tenant_id: str | None,
        input_tokens: int,
        output_tokens: int,
        model: str,
        cost: float | None = None,
    ) -> None:
        """Record token consumption across all budget dimensions."""
        total_tokens = input_tokens + output_tokens
        if cost is None:
            cost = estimate_cost(input_tokens, output_tokens, model)

        # Session tokens (TTL = 24h, sessions rarely last longer)
        sess_tok_key = self._key("sess_tok", session_id)
        await self._incr(sess_tok_key, total_tokens, ttl=86400)

        # Session cost
        sess_cost_key = self._key("sess_cost", session_id)
        await self._incr(sess_cost_key, cost, ttl=86400)

        # User hourly tokens (TTL = 1 hour)
        user_hour_key = self._key("user_hr", f"{user_id}:{int(time.time() // 3600)}")
        await self._incr(user_hour_key, total_tokens, ttl=3600)

        # Tenant daily cost (TTL = 24 hours)
        if tenant_id:
            day_key = self._key(
                "tenant_day", f"{tenant_id}:{int(time.time() // 86400)}"
            )
            await self._incr(day_key, cost, ttl=86400)

            # Tenant monthly cost (TTL = 32 days, covers longest month + buffer)
            month_key = self._key(
                "tenant_month", f"{tenant_id}:{time.strftime('%Y-%m')}"
            )
            await self._incr(month_key, cost, ttl=2764800)  # 32 days

        logger.debug(
            f"[TokenBudget] Recorded: session={session_id} "
            f"tokens={total_tokens} cost=${cost:.4f} model={model}"
        )

    async def get_session_usage(self, session_id: str) -> UsageSummary:
        """Get usage summary for a session."""
        sess_tokens = await self._get(self._key("sess_tok", session_id))
        sess_cost = await self._get(self._key("sess_cost", session_id))
        return UsageSummary(
            session_total_tokens=int(sess_tokens),
            session_cost_usd=sess_cost,
        )

    async def check_request_cost(self, estimated_cost: float) -> bool:
        """Pre-call cost gate: check if a single LLM request would exceed the hard cost cap.

        Returns True if the request is allowed, False if it should be downgraded.
        """
        if estimated_cost <= 0:
            return True
        return estimated_cost <= settings.LLM_MAX_COST_PER_REQUEST


# Module-level singleton
token_budget_manager = TokenBudgetManager()
