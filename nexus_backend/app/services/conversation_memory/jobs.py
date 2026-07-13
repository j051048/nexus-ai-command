"""Durable outbox for post-response memory extraction."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.database import supabase
from app.services.encryption_service import encryption_service

from .admission import sanitize_tool_arguments

logger = logging.getLogger(__name__)


def _safe_tool_calls(tool_calls: list[dict] | None) -> list[dict]:
    rows: list[dict] = []
    for call in (tool_calls or [])[:20]:
        if not isinstance(call, dict):
            continue
        rows.append(
            {
                "tool_name": call.get("tool_name") or call.get("name") or "",
                "args": sanitize_tool_arguments(call.get("args") or {}),
                "result": str(call.get("result") or "")[:1000],
            }
        )
    return rows


async def enqueue_memory_persistence_job(
    *,
    user_id: str,
    org_id: str,
    session_id: str,
    user_message: str,
    assistant_response: str,
    agent_name: str | None,
    metadata: dict | None,
    completed_tool_calls: list[dict] | None,
    skip_cache: bool,
    skip_semantic: bool,
    db: Any = None,
) -> str:
    client = db or supabase
    if not client:
        raise RuntimeError("Memory outbox database is unavailable")

    payload = {
        "user_id": user_id,
        "org_id": org_id,
        "session_id": session_id,
        "user_message": user_message,
        "assistant_response": assistant_response,
        "agent_name": agent_name,
        "metadata": sanitize_tool_arguments(metadata or {}),
        "completed_tool_calls": _safe_tool_calls(completed_tool_calls),
        "skip_cache": skip_cache,
        "skip_semantic": skip_semantic,
    }
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    ciphertext = encryption_service.encrypt(plaintext)
    idempotency_key = hashlib.sha256(
        f"{user_id}:{session_id}:{user_message}:{assistant_response}".encode()
    ).hexdigest()
    row = {
        "organization_id": org_id,
        "user_id": user_id,
        "session_id": session_id,
        "idempotency_key": idempotency_key,
        "payload": {"ciphertext": ciphertext},
        "status": "queued",
    }
    try:
        result = await client.table("memory_persistence_jobs").insert(row).execute()
        saved = result.data[0] if isinstance(result.data, list) else result.data
        job_id = str(saved["id"])
    except Exception as exc:
        if "duplicate" not in str(exc).lower() and "23505" not in str(exc):
            raise
        existing = (
            await client.table("memory_persistence_jobs")
            .select("id")
            .eq("idempotency_key", idempotency_key)
            .maybe_single()
            .execute()
        )
        if not existing.data:
            raise
        job_id = str(existing.data["id"])

    try:
        from app.tasks.memory_tasks import process_memory_persistence_job

        process_memory_persistence_job.delay(job_id)
    except Exception:
        logger.warning("Memory job queued; Celery dispatch deferred to periodic drain")
    return job_id


async def claim_memory_job(job_id: str | None = None) -> dict | None:
    if not supabase:
        return None
    result = await supabase.rpc(
        "claim_memory_persistence_job", {"p_job_id": job_id}
    ).execute()
    if not result.data:
        return None
    return result.data[0] if isinstance(result.data, list) else result.data


async def run_claimed_memory_job(job: dict) -> None:
    if not supabase:
        raise RuntimeError("Database unavailable")
    job_id = str(job["id"])
    attempts = int(job.get("attempts") or 1)
    try:
        ciphertext = (job.get("payload") or {}).get("ciphertext", "")
        payload = json.loads(encryption_service.decrypt(ciphertext))
        from app.agent.memory.persistence import persist_result

        await persist_result(
            **payload,
            db_client=supabase,
            persist_messages=False,
            defer_extraction=False,
        )
        await supabase.table("memory_persistence_jobs").update(
            {
                "status": "completed",
                "completed_at": datetime.now(UTC).isoformat(),
                "last_error": None,
            }
        ).eq("id", job_id).execute()
    except Exception as exc:
        terminal = attempts >= 5
        await supabase.table("memory_persistence_jobs").update(
            {
                "status": "dead_letter" if terminal else "failed",
                "last_error": str(exc)[:1000],
                "available_at": (
                    datetime.now(UTC) + timedelta(seconds=min(300, 2**attempts * 10))
                ).isoformat(),
            }
        ).eq("id", job_id).execute()
        raise
