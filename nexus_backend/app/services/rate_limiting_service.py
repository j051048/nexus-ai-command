"""
Tiered rate limiting service with per-endpoint and per-role configuration.

Provides configurable rate limits based on user/org subscription tiers,
complementing the global RateLimitMiddleware in core/rate_limiter.py.
"""

import contextlib
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class RateTier(Enum):
    """Subscription tier for rate limiting."""

    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


@dataclass
class TierLimits:
    """Per-endpoint rate limits for a specific tier."""

    chat_per_minute: int = 10
    upload_per_minute: int = 5
    auth_per_minute: int = 20
    api_per_minute: int = 60
    export_per_minute: int = 5


DEFAULT_TIER_LIMITS: dict[RateTier, TierLimits] = {
    RateTier.FREE: TierLimits(
        chat_per_minute=5,
        upload_per_minute=2,
        auth_per_minute=10,
        api_per_minute=30,
        export_per_minute=2,
    ),
    RateTier.BASIC: TierLimits(
        chat_per_minute=15,
        upload_per_minute=10,
        auth_per_minute=20,
        api_per_minute=60,
        export_per_minute=5,
    ),
    RateTier.PREMIUM: TierLimits(
        chat_per_minute=30,
        upload_per_minute=20,
        auth_per_minute=30,
        api_per_minute=120,
        export_per_minute=10,
    ),
    RateTier.ENTERPRISE: TierLimits(
        chat_per_minute=100,
        upload_per_minute=50,
        auth_per_minute=60,
        api_per_minute=300,
        export_per_minute=30,
    ),
}


@dataclass
class RateLimitEvent:
    """Records a rate limit event for auditing."""

    user_id: str
    endpoint: str
    tier: str
    allowed: bool
    timestamp: str = ""


class RateLimitingService:
    """Tiered rate limiting with org/user-level configuration.

    Manages per-tier rate limit definitions and resolves user tiers.
    The actual enforcement still uses core/rate_limiter.py's RateLimiter.
    """

    def __init__(self):
        self._tier_cache: dict[str, RateTier] = {}
        self._event_log: list = []

    async def get_user_tier(self, user_id: str, db=None) -> RateTier:
        """Resolve user's rate limiting tier."""
        if user_id in self._tier_cache:
            return self._tier_cache[user_id]

        tier = RateTier.BASIC  # Default tier
        if db:
            try:
                res = await db.table("users").select("tier").eq("id", user_id).maybe_single().execute()
                if res.data and res.data.get("tier"):
                    with contextlib.suppress(ValueError):
                        tier = RateTier(res.data["tier"])
            except Exception as e:
                logger.error(f"Tier lookup failed for {user_id}: {e}")

        self._tier_cache[user_id] = tier
        return tier

    def get_limits(self, tier: RateTier) -> TierLimits:
        """Get rate limits for a specific tier."""
        return DEFAULT_TIER_LIMITS.get(tier, DEFAULT_TIER_LIMITS[RateTier.BASIC])

    def get_endpoint_limit(self, tier: RateTier, endpoint: str) -> int:
        """Get the rate limit for a specific endpoint and tier."""
        limits = self.get_limits(tier)
        endpoint_map = {
            "chat": limits.chat_per_minute,
            "upload": limits.upload_per_minute,
            "auth": limits.auth_per_minute,
            "export": limits.export_per_minute,
        }
        return endpoint_map.get(endpoint, limits.api_per_minute)

    def invalidate_cache(self, user_id: str):
        """Clear cached tier for a user (e.g., after plan change)."""
        self._tier_cache.pop(user_id, None)

    def log_event(self, event: RateLimitEvent):
        """Log a rate limiting event for auditing."""
        self._event_log.append(event)
        if len(self._event_log) > 10000:
            self._event_log = self._event_log[-5000:]

    def get_stats(self) -> dict:
        """Get rate limiting statistics."""
        total = len(self._event_log)
        blocked = sum(1 for e in self._event_log if not e.allowed)
        return {
            "total_events": total,
            "blocked_events": blocked,
            "block_rate": blocked / max(total, 1),
        }


# Global instance
rate_limiting_service = RateLimitingService()
