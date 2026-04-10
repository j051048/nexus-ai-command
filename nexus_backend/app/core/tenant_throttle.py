"""
Item 59: Noisy-Neighbor Prevention — Tenant LLM Throttle

Provides fair-share scheduling for concurrent LLM requests across tenants.
When a single tenant exceeds MAX_CONCURRENT_LLM_PER_TENANT, new requests
are queued and dispatched via round-robin across waiting tenants.

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


class TenantThrottle:
    """
    Fair-share concurrency limiter for LLM requests, per tenant.

    - Each tenant gets at most `max_concurrent` simultaneous LLM requests.
    - When a tenant exceeds the limit, new requests are queued.
    - A simple round-robin scheduler drains queues fairly when slots free up.
    """

    def __init__(self, max_concurrent: int | None = None):
        self.max_concurrent = max_concurrent or settings.MAX_CONCURRENT_LLM_PER_TENANT
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
        Blocks if the tenant has reached its concurrent limit.
        """
        await self._wait_for_slot(tenant_id)
        try:
            yield
        finally:
            await self._release_slot(tenant_id)

    async def _wait_for_slot(self, tenant_id: str) -> None:
        """Wait until a concurrency slot is available for this tenant."""
        async with self._lock:
            if self._active[tenant_id] < self.max_concurrent:
                self._active[tenant_id] += 1
                return

            # Tenant is at capacity — create a waiter event
            waiter = asyncio.Event()
            self._waiters[tenant_id].append(waiter)

            # Register for round-robin if not already present
            if tenant_id not in self._rr_tenants:
                self._rr_tenants.append(tenant_id)

        # Wait outside the lock to avoid blocking other tenants
        logger.debug(
            f"[TenantThrottle] Tenant {tenant_id} queued "
            f"(active={self._active[tenant_id]}, waiting={len(self._waiters[tenant_id])})"
        )
        await waiter.wait()

    async def _release_slot(self, tenant_id: str) -> None:
        """Release a concurrency slot and wake the next waiter (fair-share)."""
        async with self._lock:
            self._active[tenant_id] = max(0, self._active[tenant_id] - 1)

            # Clean up empty entries
            if self._active[tenant_id] == 0 and not self._waiters.get(tenant_id):
                self._active.pop(tenant_id, None)
                self._waiters.pop(tenant_id, None)

            # Fair-share: try to wake a waiter using round-robin
            self._dispatch_next()

    def _dispatch_next(self) -> None:
        """
        Round-robin dispatch: cycle through tenants with pending waiters
        and wake one waiter from the first eligible tenant.
        Must be called with self._lock held.
        """
        if not self._rr_tenants:
            return

        # Try each tenant in round-robin order
        tried = 0
        while tried < len(self._rr_tenants):
            tenant_id = self._rr_tenants[0]
            self._rr_tenants.rotate(-1)  # Move to back of queue
            tried += 1

            waiters = self._waiters.get(tenant_id)
            if not waiters:
                # No more waiters — remove from round-robin
                self._rr_tenants.remove(tenant_id)
                continue

            if self._active[tenant_id] < self.max_concurrent:
                waiter = waiters.popleft()
                self._active[tenant_id] += 1
                waiter.set()  # Wake the waiting coroutine
                logger.debug(
                    f"[TenantThrottle] Dispatched slot to tenant {tenant_id} "
                    f"(active={self._active[tenant_id]})"
                )

                # Clean up empty waiter queue
                if not waiters:
                    self._rr_tenants.remove(tenant_id)
                    del self._waiters[tenant_id]
                return

    # ── Observability ─────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return current throttle statistics for monitoring."""
        return {
            "max_concurrent_per_tenant": self.max_concurrent,
            "active_tenants": {k: v for k, v in self._active.items() if v > 0},
            "queued_tenants": {k: len(v) for k, v in self._waiters.items() if v},
            "total_active": sum(self._active.values()),
            "total_queued": sum(len(v) for v in self._waiters.values()),
        }


# Singleton instance
tenant_throttle = TenantThrottle()
