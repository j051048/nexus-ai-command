"""
Item 59: Noisy-Neighbor Prevention — Tenant LLM Throttle

Provides fair-share scheduling for concurrent LLM requests across tenants.
When a single tenant exceeds MAX_CONCURRENT_LLM_PER_TENANT, new requests
are queued and dispatched via round-robin across waiting tenants.

P0 Enhancement: Added GLOBAL_MAX_CONCURRENT_LLM to prevent total system
LLM request count from exhausting all uvicorn workers.

Usage:
    from app.core.tenant_throttle import tenant_throttle

    async with tenant_throttle.acquire(tenant_id):
        # LLM call here — slot is held until context exits
        result = await call_llm(...)
"""

import asyncio
import logging
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from app.core.config import settings

logger = logging.getLogger(__name__)

# P0: Global system-wide LLM concurrency limit.
# Prevents all tenants combined from consuming all uvicorn workers.
GLOBAL_MAX_CONCURRENT_LLM = getattr(settings, "GLOBAL_MAX_CONCURRENT_LLM", 50)


class TenantThrottle:
    """
    Fair-share concurrency limiter for LLM requests, per tenant + global.

    - Each tenant gets at most `max_concurrent` simultaneous LLM requests.
    - System-wide total is capped at `global_max` to prevent worker exhaustion.
    - When a tenant exceeds the limit, new requests are queued.
    - A simple round-robin scheduler drains queues fairly when slots free up.
    """

    def __init__(
        self,
        max_concurrent: int | None = None,
        global_max: int | None = None,
        queue_timeout: float = 120,
    ):
        self.max_concurrent = max_concurrent or settings.MAX_CONCURRENT_LLM_PER_TENANT
        self._global_max = global_max or GLOBAL_MAX_CONCURRENT_LLM
        if min(self.max_concurrent, self._global_max, queue_timeout) <= 0:
            raise ValueError("Concurrency limits and queue timeout must be positive")
        self.queue_timeout = queue_timeout
        # tenant_id -> current active count
        self._active: dict[str, int] = defaultdict(int)
        # tenant_id -> queue of asyncio.Event objects waiting for a slot
        self._waiters: dict[str, deque[asyncio.Event]] = defaultdict(deque)
        # Round-robin pointer for fair scheduling
        self._rr_tenants: deque[str] = deque()
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self, tenant_id: str):
        """
        Async context manager that acquires a concurrency slot for the tenant.
        Blocks if the global system limit OR per-tenant limit is reached.

        Queued requests do not reserve global capacity before tenant admission.
        """
        await self._wait_for_slot(tenant_id)
        try:
            yield
        finally:
            await self._release_slot(tenant_id)

    async def _wait_for_slot(self, tenant_id: str) -> None:
        """Wait until a concurrency slot is available for this tenant."""
        waiter = asyncio.Event()
        async with self._lock:
            self._waiters[tenant_id].append(waiter)
            if tenant_id not in self._rr_tenants:
                self._rr_tenants.append(tenant_id)
            self._dispatch_next()
        try:
            async with asyncio.timeout(self.queue_timeout):
                await waiter.wait()
        except BaseException:
            async with self._lock:
                # Cancellation can race with admission: return an already granted slot.
                if waiter.is_set():
                    self._active[tenant_id] -= 1
                else:
                    self._waiters[tenant_id].remove(waiter)
                self._prune(tenant_id)
                self._dispatch_next()
            raise

    async def _release_slot(self, tenant_id: str) -> None:
        """Release a concurrency slot and wake the next waiter (fair-share)."""
        async with self._lock:
            self._active[tenant_id] = max(0, self._active[tenant_id] - 1)

            self._prune(tenant_id)
            self._dispatch_next()

    def _prune(self, tenant_id: str) -> None:
        if not self._active.get(tenant_id):
            self._active.pop(tenant_id, None)
        if not self._waiters.get(tenant_id):
            self._waiters.pop(tenant_id, None)
            if tenant_id in self._rr_tenants:
                self._rr_tenants.remove(tenant_id)

    def _dispatch_next(self) -> None:
        """
        Round-robin dispatch: cycle through tenants with pending waiters
        and wake one waiter from the first eligible tenant.
        Must be called with self._lock held.
        """
        while self._rr_tenants and sum(self._active.values()) < self._global_max:
            for _ in range(len(self._rr_tenants)):
                tenant_id = self._rr_tenants[0]
                self._rr_tenants.rotate(-1)
                if self._active.get(tenant_id, 0) >= self.max_concurrent:
                    continue
                waiter = self._waiters[tenant_id].popleft()
                self._active[tenant_id] += 1
                waiter.set()
                self._prune(tenant_id)
                break
            else:
                break

    # ── Observability ─────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return current throttle statistics for monitoring."""
        return {
            "max_concurrent_per_tenant": self.max_concurrent,
            "global_max_concurrent": self._global_max,
            "global_active": sum(self._active.values()),
            "active_tenants": {k: v for k, v in self._active.items() if v > 0},
            "queued_tenants": {k: len(v) for k, v in self._waiters.items() if v},
            "total_active": sum(self._active.values()),
            "total_queued": sum(len(v) for v in self._waiters.values()),
        }


# Singleton instance
tenant_throttle = TenantThrottle()
