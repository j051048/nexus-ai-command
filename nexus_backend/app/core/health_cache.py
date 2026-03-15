"""
G6: 健康探针 /health 改为 O(1) 缓存返回

后台协程每 CACHE_TTL 秒刷新一次健康状态，/health 端点直接返回缓存结果，
避免在 K8s liveness probe 高频调用时成为性能瓶颈。
"""

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class HealthCache:
    """
    Singleton health status cache with background refresh.

    get_cached_health() is O(1) — returns the last known status dict.
    The background task runs _refresh_health() every CACHE_TTL seconds.
    """

    CACHE_TTL: int = 10  # seconds between background refresh

    def __init__(self):
        self._cached_status: dict[str, Any] = {
            "status": "starting",
            "version": "",
            "environment": "",
            "checks": {},
        }
        self._last_check: float = 0.0
        self._task: asyncio.Task | None = None
        self._running = False

    def get_cached_health(self) -> dict[str, Any]:
        """Return cached health status. O(1), no I/O."""
        return self._cached_status

    def start_background_checker(self) -> None:
        """Start the background health refresh coroutine."""
        if self._task is not None and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._background_loop())
        logger.info("[HealthCache] Background health checker started (TTL=%ds)", self.CACHE_TTL)

    async def stop(self) -> None:
        """Stop the background checker gracefully."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("[HealthCache] Background health checker stopped")

    async def _background_loop(self) -> None:
        """Periodically refresh health status."""
        # Run first check immediately
        await self._refresh_health()
        while self._running:
            try:
                await asyncio.sleep(self.CACHE_TTL)
                if not self._running:
                    break
                await self._refresh_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("[HealthCache] Refresh error: %s", e)
                # Don't crash the loop — keep old cached status
                await asyncio.sleep(self.CACHE_TTL)

    async def _refresh_health(self) -> None:
        """Execute actual health checks and update cache."""
        from app.core.config import settings
        from app.core.database import supabase
        from app.services.cache_service import cache_service

        async def check_db() -> str:
            try:
                if not supabase:
                    return "not_configured"
                await asyncio.wait_for(
                    supabase.table("users").select("count", count="exact").limit(1).execute(),
                    timeout=2.0,
                )
                return "connected"
            except Exception as e:
                logger.warning("Health check DB error: %s", e)
                return "error" if settings.IS_PRODUCTION else f"error: {str(e)[:50]}"

        async def check_cache() -> str:
            try:
                ok = await asyncio.wait_for(cache_service.ping(), timeout=2.0)
                return "connected" if ok else "error"
            except Exception as e:
                return "error" if settings.IS_PRODUCTION else f"error: {str(e)[:50]}"

        async def check_ai() -> str:
            try:
                import httpx

                base_url = settings.AI_BASE_URL or "https://api.openai.com/v1"
                domain = base_url.split("/v1")[0].split("/chat")[0]
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.get(domain)
                    return f"reachable ({resp.status_code})"
            except Exception as e:
                return "unreachable" if settings.IS_PRODUCTION else f"unreachable: {str(e)[:50]}"

        async def check_llm_gateway() -> str:
            try:
                if not supabase:
                    return "not_configured"
                model_res = await asyncio.wait_for(
                    supabase.table("llm_model_config")
                    .select("id", count="exact")
                    .eq("status", "enabled")
                    .eq("is_deleted", False)
                    .execute(),
                    timeout=2.0,
                )
                enabled_count = model_res.count if model_res.count is not None else len(model_res.data or [])
                return f"ok ({enabled_count} models)" if enabled_count > 0 else "no_models_enabled"
            except Exception:
                return "available"

        # Run all checks concurrently
        db_status, cache_status, ai_status, llm_gw_status = await asyncio.gather(
            check_db(), check_cache(), check_ai(), check_llm_gateway()
        )

        is_healthy = db_status == "connected" and cache_status == "connected"

        self._cached_status = {
            "status": "healthy" if is_healthy else "degraded",
            "version": settings.VERSION,
            "environment": settings.ENV,
            "checks": {
                "database": db_status,
                "cache": cache_status,
                "ai_gateway": ai_status,
                "llm_model_gateway": llm_gw_status,
            },
            "_http_status": 200 if is_healthy else 503,
        }
        self._last_check = time.monotonic()
        logger.debug("[HealthCache] Refreshed: %s", "healthy" if is_healthy else "degraded")


# Module-level singleton
health_cache = HealthCache()
