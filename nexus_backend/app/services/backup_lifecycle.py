"""Background sweeps that turn backup intent into executed backups.

``backup_schedules`` has always described intent: an operator picks a
frequency, the UI reports "daily", an index on ``next_backup_at`` exists - and
nothing ever polled it. This module is that poller, plus the expiry sweep that
removes backups past ``expires_at`` along with their off-site objects.

Both sweeps are safe to run on every beat tick and from multiple workers:
claiming a schedule is a compare-and-set on ``next_backup_at``, so a losing
racer sees an empty update and skips that organization.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.services.backup_service import (
    RECOVERABLE_BACKUP_ERRORS,
    backup_service,
    service_client,
)

logger = logging.getLogger(__name__)


def _next_backup_at(frequency: str | None, after: datetime) -> datetime:
    if frequency == "weekly":
        return after + timedelta(weeks=1)
    if frequency == "monthly":
        return after + timedelta(days=30)
    return after + timedelta(days=1)


async def expire_expired_backups(db=None, now: datetime | None = None) -> dict:
    """Delete backup records whose ``expires_at`` has passed."""
    client = db or service_client()
    if not client:
        return {"expired": 0, "checked": 0}

    moment = now or datetime.now(UTC)
    result = (
        await client.table("backup_records")
        .select("id, organization_id, storage_backend, storage_ref, expires_at")
        .not_.is_("expires_at", "null")
        .lt("expires_at", moment.isoformat())
        .execute()
    )
    rows = result.data or []
    deleted = await backup_service.delete_records(client, rows)
    logger.info(
        "[Backup] expiry sweep finished: expired=%d checked=%d", deleted, len(rows)
    )
    return {"expired": deleted, "checked": len(rows)}


async def _claim_schedule(db, row: dict, now: datetime) -> str | None:
    """Claim one due schedule, returning the next run time when we won."""
    next_run = _next_backup_at(row.get("frequency"), now)
    organization_id = row.get("organization_id")
    claim = (
        await db.table("backup_schedules")
        .update(
            {
                "next_backup_at": next_run.isoformat(),
                "claimed_at": now.isoformat(),
                "last_status": "running",
                "last_error": None,
            }
        )
        .eq("id", row["id"])
        # Bound to the tenant as well as the id: the claim is the point where a
        # buggy cross-tenant write would corrupt another organization's cadence.
        .eq("organization_id", organization_id)
        .eq("next_backup_at", row.get("next_backup_at"))
        .execute()
    )
    return next_run.isoformat() if claim.data else None


async def run_due_backup_schedules(
    db=None, now: datetime | None = None, limit: int | None = None
) -> dict:
    """Execute every backup schedule that is due."""
    client = db or service_client()
    if not client:
        return {"due": 0, "completed": 0, "failed": 0, "skipped": 0}

    moment = now or datetime.now(UTC)
    batch_limit = int(limit or getattr(settings, "BACKUP_SCHEDULE_BATCH_LIMIT", 10))
    due = (
        await client.table("backup_schedules")
        .select("id, organization_id, frequency, tables, is_active, next_backup_at")
        .eq("is_active", True)
        .lte("next_backup_at", moment.isoformat())
        .order("next_backup_at")
        .limit(batch_limit)
        .execute()
    )
    rows = due.data or []
    counters = {"due": len(rows), "completed": 0, "failed": 0, "skipped": 0}

    for row in rows:
        org_id = row.get("organization_id")
        claimed_next = await _claim_schedule(client, row, moment)
        if not claimed_next:
            counters["skipped"] += 1
            continue
        try:
            created = await backup_service.create_backup(
                org_id=org_id,
                tables=row.get("tables"),
                backup_type="auto",
                db=client,
            )
        except RECOVERABLE_BACKUP_ERRORS as exc:
            counters["failed"] += 1
            logger.error("[Backup] scheduled backup failed org=%s: %s", org_id, exc)
            await (
                client.table("backup_schedules")
                .update(
                    {
                        "last_status": "failed",
                        "last_error": str(exc)[:500],
                        "claimed_at": None,
                    }
                )
                .eq("id", row["id"])
                .eq("organization_id", row.get("organization_id"))
                .execute()
            )
            continue

        counters["completed"] += 1
        await (
            client.table("backup_schedules")
            .update(
                {
                    "last_status": "completed",
                    "last_error": None,
                    "last_backup_at": moment.isoformat(),
                    "last_backup_id": created.get("id"),
                    "next_backup_at": claimed_next,
                    "claimed_at": None,
                }
            )
            .eq("id", row["id"])
            .eq("organization_id", row.get("organization_id"))
            .execute()
        )

    logger.info(
        "[Backup] schedule sweep finished: due=%d completed=%d failed=%d skipped=%d",
        counters["due"],
        counters["completed"],
        counters["failed"],
        counters["skipped"],
    )
    return counters
