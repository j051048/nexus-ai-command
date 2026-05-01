"""
Celery Dead Letter Queue — records task failures and supports replay.

Usage:
    from app.tasks.dlq import write_dead_letter, replay_dead_letters

    # Automatic: NexusTask.on_failure calls write_dead_letter
    # Manual replay:
    #   await replay_dead_letters(task_name="run_daily_report", limit=5)
"""

import json
import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


def write_dead_letter(
    *,
    task_name: str,
    task_id: str,
    args: tuple | list | None = None,
    kwargs: dict | None = None,
    exception: str = "",
    traceback: str = "",
    retries: int = 0,
    max_retries: int = 0,
) -> None:
    """Synchronously write a dead letter record.

    Called from Celery worker (sync context) via NexusTask.on_failure.
    Uses httpx sync to POST to Supabase REST API.
    """
    import os

    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        logger.warning("[DLQ] SUPABASE_URL/SERVICE_KEY not set, skipping DLQ write")
        return

    row = {
        "task_name": task_name,
        "task_id": task_id,
        "args": json.dumps(args or [], ensure_ascii=False),
        "kwargs": json.dumps(kwargs or {}, ensure_ascii=False),
        "exception": exception[:2000],
        "traceback": traceback[:4000],
        "retries": retries,
        "max_retries": max_retries,
        "status": "dead",
    }

    try:
        import httpx

        resp = httpx.post(
            f"{url}/rest/v1/celery_dead_letters",
            json=row,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            timeout=10.0,
        )
        if resp.status_code >= 300:
            logger.error("[DLQ] Write failed: %s %s", resp.status_code, resp.text[:200])
        else:
            logger.info("[DLQ] Recorded dead letter: %s [%s]", task_name, task_id[:8])
    except Exception as e:
        logger.error("[DLQ] Write exception: %s", e)


async def replay_dead_letters(
    task_name: str | None = None,
    limit: int = 10,
    db=None,
) -> list[dict]:
    """Replay dead letters by re-sending them to Celery.

    Returns list of replayed records with their new task IDs.
    """
    from app.core.celery_app import celery_app
    from app.core.database import supabase

    client = db or supabase
    query = (
        client.table("celery_dead_letters")
        .select("*")
        .eq("status", "dead")
        .order("created_at", desc=False)
        .limit(limit)
    )
    if task_name:
        query = query.eq("task_name", task_name)

    res = await query.execute()
    rows = res.data or []
    if not rows:
        return []

    replayed = []
    for row in rows:
        try:
            args = row.get("args") or []
            kwargs = row.get("kwargs") or {}
            if isinstance(args, str):
                args = json.loads(args)
            if isinstance(kwargs, str):
                kwargs = json.loads(kwargs)

            result = celery_app.send_task(row["task_name"], args=args, kwargs=kwargs)
            await (
                client.table("celery_dead_letters")
                .update(
                    {
                        "status": "replayed",
                        "replayed_at": datetime.now(UTC).isoformat(),
                    }
                )
                .eq("id", row["id"])
                .execute()
            )
            replayed.append(
                {
                    "dlq_id": row["id"],
                    "task_name": row["task_name"],
                    "new_task_id": result.id,
                }
            )
            logger.info("[DLQ] Replayed: %s → %s", row["task_name"], result.id)
        except Exception as e:
            logger.error("[DLQ] Replay failed for %s: %s", row["id"], e)

    return replayed
