"""Enforce the retention windows the compliance API advertises.

``GET /api/compliance/retention`` used to return hardcoded numbers ("audit
logs 365 days, chat history 90 days, usage 180 days") with no job behind them:
declared policy, no execution. This module makes the windows real and keeps an
auditable record of every sweep.

Enforcement is off unless ``DATA_RETENTION_ENFORCEMENT_ENABLED`` is set, because
deleting customer data must be a deliberate operator decision. While it is off,
the API reports ``enforced=false`` instead of implying the policy runs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from postgrest.exceptions import APIError as PostgrestAPIError

from app.core.config import settings

logger = logging.getLogger(__name__)

#: Upper bound on batches per policy per sweep, so one run cannot scan forever.
MAX_BATCHES_PER_POLICY = 20

#: Upper bound on organizations handled per policy per sweep.
MAX_ORGS_PER_SWEEP = 200

#: Database, transport and row-shape failures that belong to one policy. Kept
#: specific on purpose: a broad catch would let a broken sweep report success.
_RETENTION_SWEEP_ERRORS = (
    PostgrestAPIError,
    httpx.HTTPError,
    TimeoutError,
    OSError,
    RuntimeError,
    KeyError,
    TypeError,
    ValueError,
)


@dataclass(frozen=True)
class RetentionPolicy:
    data_type: str
    table: str
    time_column: str
    org_column: str
    settings_field: str
    description: str

    def window_days(self, source: Any) -> int:
        return int(getattr(source, self.settings_field))


RETENTION_POLICIES: tuple[RetentionPolicy, ...] = (
    RetentionPolicy(
        data_type="audit_logs",
        table="audit_logs",
        time_column="timestamp",
        org_column="org_id",
        settings_field="DATA_RETENTION_AUDIT_LOG_DAYS",
        description="审计日志保留 1 年",
    ),
    RetentionPolicy(
        data_type="chat_history",
        table="chat_messages",
        time_column="created_at",
        org_column="organization_id",
        settings_field="DATA_RETENTION_CHAT_MESSAGE_DAYS",
        description="会话消息保留 90 天",
    ),
    RetentionPolicy(
        data_type="token_usage",
        table="user_token_usage",
        time_column="created_at",
        org_column="org_id",
        settings_field="DATA_RETENTION_TOKEN_USAGE_DAYS",
        description="用量数据保留 6 个月",
    ),
)


def enforcement_enabled(source: Any | None = None) -> bool:
    return bool(
        getattr(source or settings, "DATA_RETENTION_ENFORCEMENT_ENABLED", False)
    )


def policy_snapshot(source: Any | None = None) -> list[dict[str, Any]]:
    """Describe the configured windows plus whether they are actually applied."""
    config = source or settings
    enabled = enforcement_enabled(config)
    return [
        {
            "data_type": policy.data_type,
            "retention_days": policy.window_days(config),
            "table": policy.table,
            "description": policy.description,
            "enforced": enabled,
        }
        for policy in RETENTION_POLICIES
    ]


def _service_client():
    from app.core.database import supabase

    return supabase


async def _organization_ids(db, limit: int = MAX_ORGS_PER_SWEEP) -> list[str]:
    """List the tenants a sweep may touch.

    Retention runs per organization on purpose: one tenant's malformed data or
    missing index cannot widen the blast radius to everyone else, and every
    delete stays bound to a single organization id.
    """
    result = (
        await db.table("organizations").select("id").order("id").limit(limit).execute()
    )
    return [row["id"] for row in (result.data or []) if row.get("id")]


async def _delete_org_batch(
    db,
    policy: RetentionPolicy,
    organization_id: str,
    cutoff: datetime,
    batch_size: int,
) -> int:
    """Delete one bounded batch for one organization.

    Counting through ``delete().execute().data`` depends on the provider
    returning a representation; selecting ids first makes the sweep
    deterministic and works the same on every PostgREST version.
    """
    cutoff_iso = cutoff.isoformat()
    selected = (
        await db.table(policy.table)
        .select("id")
        .eq(policy.org_column, organization_id)
        .lt(policy.time_column, cutoff_iso)
        .limit(batch_size)
        .execute()
    )
    ids = [row["id"] for row in (selected.data or []) if row.get("id") is not None]
    if not ids:
        return 0
    await (
        db.table(policy.table)
        .delete()
        .eq(policy.org_column, organization_id)
        .in_("id", ids)
        .execute()
    )
    return len(ids)


async def enforce_policy(
    policy: RetentionPolicy,
    db,
    now: datetime,
    batch_size: int,
    organization_ids: list[str],
) -> dict[str, Any]:
    days = policy.window_days(settings)
    cutoff = now - timedelta(days=days)
    deleted = 0
    for organization_id in organization_ids:
        for _ in range(MAX_BATCHES_PER_POLICY):
            batch = await _delete_org_batch(
                db, policy, organization_id, cutoff, batch_size
            )
            deleted += batch
            if batch < batch_size:
                break
    return {
        "data_type": policy.data_type,
        "retention_days": days,
        "cutoff": cutoff.isoformat(),
        "deleted_rows": deleted,
        "organizations": len(organization_ids),
    }


async def enforce_data_retention(
    db=None, now: datetime | None = None
) -> dict[str, Any]:
    """Apply every configured retention window once."""
    if not enforcement_enabled():
        logger.info(
            "[Retention] enforcement disabled; set "
            "DATA_RETENTION_ENFORCEMENT_ENABLED=true to apply the declared windows"
        )
        return {"enabled": False, "runs": []}

    client = db or _service_client()
    if not client:
        return {"enabled": True, "runs": [], "error": "数据库连接不可用"}

    moment = now or datetime.now(UTC)
    batch_size = int(getattr(settings, "DATA_RETENTION_BATCH_SIZE", 500))
    runs: list[dict[str, Any]] = []
    organization_ids = await _organization_ids(client)
    if not organization_ids:
        logger.info("[Retention] no organizations to sweep")
        return {"enabled": True, "runs": [], "deleted_rows": 0}

    for policy in RETENTION_POLICIES:
        started = datetime.now(UTC)
        try:
            outcome = await enforce_policy(
                policy, client, moment, batch_size, organization_ids
            )
            status = "completed"
            error_message = None
        except _RETENTION_SWEEP_ERRORS as exc:
            # A single unreadable table must not abort the other policies.
            outcome = {
                "data_type": policy.data_type,
                "retention_days": policy.window_days(settings),
                "cutoff": (
                    moment - timedelta(days=policy.window_days(settings))
                ).isoformat(),
                "deleted_rows": 0,
                "organizations": len(organization_ids),
            }
            status = "failed"
            error_message = str(exc)[:500]
            logger.error("[Retention] %s failed: %s", policy.data_type, exc)

        finished = datetime.now(UTC)
        runs.append({**outcome, "status": status})
        try:
            await (
                client.table("data_retention_runs")
                .insert(
                    {
                        "data_type": policy.data_type,
                        "retention_days": outcome["retention_days"],
                        "cutoff": outcome["cutoff"],
                        "deleted_rows": outcome["deleted_rows"],
                        "status": status,
                        "error_message": error_message,
                        "started_at": started.isoformat(),
                        "finished_at": finished.isoformat(),
                    }
                )
                .execute()
            )
        except _RETENTION_SWEEP_ERRORS as exc:
            logger.warning(
                "[Retention] could not record run for %s: %s", policy.data_type, exc
            )

    total_deleted = sum(run["deleted_rows"] for run in runs)
    logger.info(
        "[Retention] sweep finished: policies=%d deleted_rows=%d",
        len(runs),
        total_deleted,
    )
    await _record_audit(runs)
    return {"enabled": True, "runs": runs, "deleted_rows": total_deleted}


async def _record_audit(runs: list[dict[str, Any]]) -> None:
    try:
        from app.services.audit_logger import audit_logger

        await audit_logger.log(
            action="retention_enforcement",
            org_id=None,
            target_table="data_retention_runs",
            details={"runs": runs},
            status="success",
        )
    except _RETENTION_SWEEP_ERRORS as exc:
        logger.warning("[Retention] audit entry skipped: %s", exc)


async def last_retention_runs(limit: int = 5, db=None) -> list[dict[str, Any]]:
    """Return the most recent sweeps so the API can report real state."""
    client = db or _service_client()
    if not client:
        return []
    try:
        result = (
            await client.table("data_retention_runs")
            .select("data_type, retention_days, deleted_rows, status, started_at")
            .order("started_at", desc=True)
            .limit(limit)
            .execute()
        )
    except _RETENTION_SWEEP_ERRORS as exc:
        logger.warning("[Retention] could not read run history: %s", exc)
        return []
    return result.data or []
