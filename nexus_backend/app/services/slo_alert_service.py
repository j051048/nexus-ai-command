"""Turn SLO breaches into alerts somebody actually receives.

The handbook defines service targets and the code exposes metrics, but an alert
that only writes a log line is not an alert: no human sees it. This service
collects breaches from the signals that already exist, de-duplicates them, and
delivers them to a webhook (Slack / 飞书 / generic JSON).

Signals covered:

* active degradations (``degradation_registry``) - Redis, cache, checkpointer;
* agent success rate below threshold (``ai_metrics``);
* backup schedules whose last run failed (``backup_schedules``);
* retention sweeps that failed (``data_retention_runs``);
* artifact-quality SLO in ``warn`` for the organizations sampled.

Delivery is de-duplicated per alert key for ``ALERT_MIN_INTERVAL_SECONDS`` and
recorded in ``ops_alert_events`` so a restart cannot re-page the same incident.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.core.config import settings
from app.core.degradation_registry import degradation_registry

logger = logging.getLogger(__name__)

CRITICAL = "critical"
WARNING = "warning"

#: Degradations that mean a production control is silently off.
_CRITICAL_DEGRADATIONS = {"token_budget_redis", "redis_cache", "checkpointer"}

#: Failures that must not take the whole sweep down.
_ALERT_ERRORS = (httpx.HTTPError, TimeoutError, OSError, RuntimeError, ValueError)


@dataclass(frozen=True)
class AlertEvent:
    key: str
    severity: str
    title: str
    detail: str
    source: str
    organization_id: str | None = None

    def as_payload(self) -> dict[str, Any]:
        return asdict(self)


def service_client():
    """Service-role client for background runs (no request context)."""
    from app.core.database import supabase

    return supabase


def collect_degradation_alerts() -> list[AlertEvent]:
    summary = degradation_registry.summary()
    events: list[AlertEvent] = []
    for service in summary.get("services") or []:
        name = str(service.get("service") or "unknown")
        severity = CRITICAL if name in _CRITICAL_DEGRADATIONS else WARNING
        events.append(
            AlertEvent(
                key=f"degradation:{name}",
                severity=severity,
                title=f"服务降级: {name}",
                detail=str(service.get("reason") or ""),
                source="degradation_registry",
            )
        )
    return events


def collect_agent_success_alerts() -> list[AlertEvent]:
    from app.core.ai_metrics import agent_success_snapshot

    snapshot = agent_success_snapshot()
    rate = snapshot.get("success_rate")
    threshold = float(settings.ALERT_AGENT_SUCCESS_RATE_THRESHOLD)
    if rate is None or int(snapshot["sample_size"]) < int(
        settings.ALERT_AGENT_MIN_SAMPLES
    ):
        return []
    if float(rate) >= threshold:
        return []
    severity = CRITICAL if float(rate) < threshold * 0.8 else WARNING
    return [
        AlertEvent(
            key="agent_success_rate",
            severity=severity,
            title="Agent 成功率低于目标",
            detail=(
                f"窗口 {int(snapshot['window_seconds'])}s 内成功率 "
                f"{float(rate) * 100:.1f}%（{snapshot['successes']}/"
                f"{snapshot['sample_size']}），目标 {threshold * 100:.0f}%"
            ),
            source="ai_metrics",
        )
    ]


async def collect_backup_alerts(db, now: datetime | None = None) -> list[AlertEvent]:
    moment = now or datetime.now(UTC)
    since = (
        moment - timedelta(hours=int(settings.ALERT_BACKUP_FAILURE_LOOKBACK_HOURS))
    ).isoformat()
    result = (
        await db.table("backup_schedules")
        .select("organization_id, last_status, last_error, claimed_at, last_backup_at")
        .eq("last_status", "failed")
        .gte("claimed_at", since)
        .limit(int(settings.ALERT_MAX_EVENTS_PER_RUN))
        .execute()
    )
    return [
        AlertEvent(
            key=f"backup_failed:{row.get('organization_id')}",
            severity=CRITICAL,
            title="计划备份执行失败",
            detail=str(row.get("last_error") or "no error detail"),
            source="backup_schedules",
            organization_id=row.get("organization_id"),
        )
        for row in (result.data or [])
    ]


async def collect_retention_alerts(db, now: datetime | None = None) -> list[AlertEvent]:
    moment = now or datetime.now(UTC)
    since = (
        moment - timedelta(hours=int(settings.ALERT_RETENTION_FAILURE_LOOKBACK_HOURS))
    ).isoformat()
    result = (
        await db.table("data_retention_runs")
        .select("data_type, status, error_message, started_at")
        .eq("status", "failed")
        .gte("started_at", since)
        .limit(int(settings.ALERT_MAX_EVENTS_PER_RUN))
        .execute()
    )
    return [
        AlertEvent(
            key=f"retention_failed:{row.get('data_type')}",
            severity=WARNING,
            title=f"数据保留清理失败: {row.get('data_type')}",
            detail=str(row.get("error_message") or "no error detail"),
            source="data_retention_runs",
        )
        for row in (result.data or [])
    ]


async def collect_quality_alerts(db, now: datetime | None = None) -> list[AlertEvent]:
    """Sample organizations and alert when the quality SLO is in ``warn``."""
    from app.services.artifact_quality_slo import evaluate_slo

    orgs = (
        await db.table("organizations")
        .select("id")
        .order("id")
        .limit(int(settings.ALERT_ORG_SAMPLE_LIMIT))
        .execute()
    )
    events: list[AlertEvent] = []
    for row in orgs.data or []:
        organization_id = row.get("id")
        if not organization_id:
            continue
        report = await evaluate_slo(db, organization_id=str(organization_id))
        if not report.get("available") or report.get("overall") != "warn":
            continue
        failing = [
            name
            for name, item in (report.get("slo") or {}).items()
            if not item.get("ok")
        ]
        events.append(
            AlertEvent(
                key=f"artifact_quality_slo:{organization_id}",
                severity=WARNING,
                title="文档交付质量 SLO 未达标",
                detail="未达标指标: " + ", ".join(sorted(failing)),
                source="artifact_quality_slo",
                organization_id=str(organization_id),
            )
        )
    return events


async def collect_alerts(db=None, now: datetime | None = None) -> list[AlertEvent]:
    """Collect every currently-breached alert rule."""
    events = collect_degradation_alerts() + collect_agent_success_alerts()
    client = db or service_client()
    if client is None:
        return events
    for collector in (
        collect_backup_alerts,
        collect_retention_alerts,
        collect_quality_alerts,
    ):
        try:
            events.extend(await collector(client, now))
        except _ALERT_ERRORS as exc:
            # A single unreadable signal must not hide the others.
            logger.warning("[Alert] %s failed: %s", collector.__name__, exc)
    return events[: int(settings.ALERT_MAX_EVENTS_PER_RUN)]


def build_webhook_payload(events: list[AlertEvent]) -> dict[str, Any]:
    """Render the configured webhook format."""
    headline = "Nexus 告警 " + ", ".join(
        f"[{event.severity}] {event.title}" for event in events
    )
    lines = "\n".join(
        f"- ({event.severity}) {event.title}: {event.detail}" for event in events
    )
    webhook_format = str(settings.ALERT_WEBHOOK_FORMAT)
    if webhook_format == "slack":
        return {"text": f"{headline}\n{lines}"}
    if webhook_format == "feishu":
        return {"msg_type": "text", "content": {"text": f"{headline}\n{lines}"}}
    return {
        "source": "nexus",
        "generated_at": datetime.now(UTC).isoformat(),
        "count": len(events),
        "events": [event.as_payload() for event in events],
    }


async def _post_webhook(url: str, payload: dict[str, Any]) -> bool:
    async with httpx.AsyncClient(
        timeout=float(settings.ALERT_WEBHOOK_TIMEOUT_SECONDS)
    ) as client:
        response = await client.post(url, json=payload)
    return 200 <= response.status_code < 300


async def dispatch_alerts(
    events: list[AlertEvent], db=None, now: datetime | None = None
) -> dict[str, Any]:
    """De-duplicate and deliver alerts; record every delivery for audit."""
    client = db or service_client()
    moment = now or datetime.now(UTC)
    counters = {
        "collected": len(events),
        "sent": 0,
        "suppressed": 0,
        "failed": 0,
        "resolved": 0,
    }
    if not events:
        return counters

    cooldown = int(settings.ALERT_MIN_INTERVAL_SECONDS)
    cutoff = (moment - timedelta(seconds=cooldown)).isoformat()
    fresh: list[AlertEvent] = []

    for event in events:
        if client is not None:
            recent = (
                await client.table("ops_alert_events")
                .select("key, organization_id, last_sent_at, resolved_at")
                .eq("key", event.key)
                .gte("last_sent_at", cutoff)
                .limit(1)
                .execute()
            )
            if recent.data:
                counters["suppressed"] += 1
                continue
        fresh.append(event)

    # Mark alerts that are no longer firing as resolved, so "已恢复" is visible
    # in the ledger instead of staying open forever.
    if client is not None:
        current_keys = {event.key for event in events}
        active = (
            await client.table("ops_alert_events")
            .select("key, organization_id")
            .is_("resolved_at", "null")
            .execute()
        )
        for row in active.data or []:
            if str(row.get("key")) in current_keys:
                continue
            await (
                client.table("ops_alert_events")
                .update({"resolved_at": moment.isoformat()})
                .eq("key", row.get("key"))
                .execute()
            )
            counters["resolved"] += 1

    if not fresh:
        return counters

    url = str(settings.ALERT_WEBHOOK_URL or "").strip()
    delivered = False
    if url and settings.ALERTING_ENABLED:
        try:
            delivered = await _post_webhook(url, build_webhook_payload(fresh))
        except _ALERT_ERRORS as exc:
            logger.error("[Alert] webhook delivery failed: %s", exc)
            delivered = False
    else:
        logger.warning(
            "[Alert] ALERT_WEBHOOK_URL is not configured; %d alert(s) were only "
            "recorded: %s",
            len(fresh),
            ", ".join(event.key for event in fresh),
        )

    for event in fresh:
        counters["sent" if delivered else "failed"] += 1
        if client is None:
            continue
        try:
            await (
                client.table("ops_alert_events")
                .upsert(
                    {
                        "key": event.key,
                        "severity": event.severity,
                        "title": event.title,
                        "detail": event.detail,
                        "source": event.source,
                        "organization_id": event.organization_id,
                        "last_sent_at": moment.isoformat(),
                        "delivered": delivered,
                    },
                    on_conflict="key",
                )
                .execute()
            )
        except _ALERT_ERRORS as exc:
            logger.warning("[Alert] could not record %s: %s", event.key, exc)
    return counters


async def evaluate_and_dispatch(db=None, now: datetime | None = None) -> dict[str, Any]:
    """Entry point used by the beat task."""
    if not settings.ALERTING_ENABLED:
        return {"enabled": False}
    started = time.perf_counter()
    events = await collect_alerts(db=db, now=now)
    counters = await dispatch_alerts(events, db=db, now=now)
    counters["enabled"] = True
    counters["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "[Alert] sweep finished: collected=%d sent=%d suppressed=%d failed=%d",
        counters["collected"],
        counters["sent"],
        counters["suppressed"],
        counters["failed"],
    )
    return counters
