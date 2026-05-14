"""Celery queue backlog monitor.

Redis broker queues are stored as Redis lists named after the queue. This
module keeps the check lightweight enough for deployment health probes while
also exporting queue depth to Prometheus.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from app.core.metrics import observe_celery_queue_depth

DEFAULT_QUEUES = (
    "default",
    "agent_tools",
    "agent_tools_high_risk",
    "webhooks",
    "sensors",
)


def _broker_url() -> str:
    return os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL") or ""


def _queue_names() -> list[str]:
    raw = os.getenv("CELERY_MONITORED_QUEUES", "")
    names = [item.strip() for item in raw.split(",") if item.strip()]
    return names or list(DEFAULT_QUEUES)


async def collect_celery_queue_health() -> dict:
    """Return queue backlog health for deployment readiness checks."""
    broker_url = _broker_url()
    warning_threshold = int(os.getenv("CELERY_QUEUE_DEPTH_WARNING", "100"))
    critical_threshold = int(os.getenv("CELERY_QUEUE_DEPTH_CRITICAL", "1000"))

    if not broker_url:
        return {
            "name": "CELERY_QUEUE_DEPTH",
            "ok": False,
            "severity": "warning",
            "value": "broker_not_configured",
            "message": "CELERY_BROKER_URL or REDIS_URL is required for queue backlog monitoring",
        }

    parsed = urlparse(broker_url)
    if parsed.scheme not in {"redis", "rediss"}:
        return {
            "name": "CELERY_QUEUE_DEPTH",
            "ok": True,
            "severity": "warning",
            "value": parsed.scheme or "unknown",
            "message": "Queue depth monitor currently supports Redis brokers only",
        }

    try:
        import redis.asyncio as redis

        client = redis.from_url(broker_url, decode_responses=True)
        try:
            depths: dict[str, int] = {}
            for queue in _queue_names():
                depth = int(await client.llen(queue))
                depths[queue] = depth
                observe_celery_queue_depth(queue, depth)
        finally:
            await client.aclose()
    except Exception as exc:
        return {
            "name": "CELERY_QUEUE_DEPTH",
            "ok": False,
            "severity": "warning",
            "value": "unavailable",
            "message": f"Failed to inspect Celery queues: {type(exc).__name__}",
        }

    max_depth = max(depths.values(), default=0)
    severity = "critical" if max_depth >= critical_threshold else "warning"
    return {
        "name": "CELERY_QUEUE_DEPTH",
        "ok": max_depth < critical_threshold,
        "severity": severity,
        "value": depths,
        "message": (
            f"max_depth={max_depth}, warning>={warning_threshold}, "
            f"critical>={critical_threshold}"
        ),
        "alert": max_depth >= warning_threshold,
    }
