"""
Unified Degradation Registry — central tracking for service fallbacks.

When any subsystem (checkpointer, cache, vector search, etc.) falls back to
a degraded mode, it registers the event here.  The /health/deep endpoint and
alerting logic can then aggregate degradation state across the whole system.
"""

import logging
import time
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class DegradationEvent:
    """A single service degradation record."""

    service: str  # e.g. "checkpointer", "redis_cache", "vector_search"
    reason: str
    timestamp: float = field(default_factory=time.time)
    fallback: str = ""  # what the service fell back to


class DegradationRegistry:
    """Thread-safe registry of active degradations.

    Usage::

        from app.core.degradation_registry import degradation_registry

        degradation_registry.register("redis_cache", "Connection refused", fallback="InMemoryCache")
        degradation_registry.resolve("redis_cache")

        # In /health/deep
        summary = degradation_registry.summary()
    """

    def __init__(self) -> None:
        self._active: dict[str, DegradationEvent] = {}
        self._lock = Lock()

    def register(self, service: str, reason: str, *, fallback: str = "") -> None:
        """Register a degradation event for a service."""
        with self._lock:
            self._active[service] = DegradationEvent(
                service=service, reason=reason, fallback=fallback,
            )
        logger.warning(
            "[Degradation] %s degraded: %s (fallback=%s)", service, reason, fallback or "none",
        )

    def resolve(self, service: str) -> None:
        """Mark a previously degraded service as recovered."""
        with self._lock:
            removed = self._active.pop(service, None)
        if removed:
            logger.info("[Degradation] %s recovered (was degraded for %.0fs)",
                        service, time.time() - removed.timestamp)

    @property
    def is_healthy(self) -> bool:
        """True if no services are currently degraded."""
        with self._lock:
            return len(self._active) == 0

    @property
    def degraded_count(self) -> int:
        with self._lock:
            return len(self._active)

    def summary(self) -> dict:
        """Return a JSON-serializable summary for health endpoints."""
        with self._lock:
            events = list(self._active.values())
        return {
            "degraded": len(events) > 0,
            "count": len(events),
            "services": [
                {
                    "service": e.service,
                    "reason": e.reason,
                    "fallback": e.fallback,
                    "since": e.timestamp,
                    "duration_s": round(time.time() - e.timestamp, 1),
                }
                for e in events
            ],
        }


# Global singleton
degradation_registry = DegradationRegistry()
