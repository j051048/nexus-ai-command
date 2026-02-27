"""
Redis Key Naming Convention Helper.

All Redis keys MUST follow the convention: {scope}:{service}:{sub_key}
where scope is typically org_id, user_id, or "global" for shared data.

This module provides:
1. `rk()` — build a key following the naming convention
2. Constants for common service namespaces

Usage:
    from app.core.redis_keys import rk

    # Per-org key
    rk("org-123", "dept", "all")        → "org-123:dept:all"

    # Per-user key
    rk("user-456", "role")              → "user-456:role"

    # Global key (no tenant isolation)
    rk(None, "health", "check")         → "global:health:check"
"""

import logging

logger = logging.getLogger(__name__)

# ─── Service Namespace Constants ──────────────────────────────────────────────
# Use these to avoid typos in cache key service names

NS_ROLE = "role"
NS_SETTINGS = "settings"
NS_PROMPT = "prompt"
NS_DEPT = "dept"
NS_DOC = "doc"
NS_IDEMPOTENCY = "idempotency"
NS_RATE_LIMIT = "rl"
NS_CONTEXT = "ctx"


def rk(scope: str | None, service: str, *parts: str) -> str:
    """
    Build a Redis key following the standard naming convention.

    Args:
        scope: Tenant identifier (org_id, user_id, etc.) or None for global.
        service: Service/domain namespace (e.g., "role", "dept", "prompt").
        *parts: Additional key segments.

    Returns:
        Formatted key string like "{scope}:{service}:{part1}:{part2}"

    Examples:
        rk("org-123", "dept", "all")         → "org-123:dept:all"
        rk("user-456", "settings")           → "user-456:settings"
        rk(None, "health", "check")          → "global:health:check"
    """
    prefix = scope or "global"
    segments = [prefix, service] + list(parts)
    return ":".join(segments)
