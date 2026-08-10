"""Durable orchestration for long-running artifact generation jobs."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import socket
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.agent.artifact_contract import ArtifactAudience, ArtifactType
from app.services.artifact_generation_service import (
    ArtifactGenerationCancelledError,
    generate_artifact,
)

logger = logging.getLogger(__name__)

TERMINAL_JOB_STATUSES = {"cancelled", "completed", "failed"}
LEASE_SECONDS = 90
HEARTBEAT_SECONDS = 20


class ArtifactJobLeaseLostError(RuntimeError):
    """Raised when another worker has taken ownership of the durable job."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def build_request_key(
    *, organization_id: str, user_id: str, payload: dict[str, Any]
) -> str:
    explicit = str(payload.pop("request_key", "") or "").strip()
    if explicit:
        return explicit[:120]
    digest = hashlib.sha256(
        json.dumps(
            {
                "organization_id": organization_id,
                "user_id": user_id,
                "payload": payload,
                "nonce": uuid4().hex,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return f"artifact-{digest[:48]}"


def public_job(row: dict[str, Any]) -> dict[str, Any]:
    result_payload = dict(row.get("result_payload") or {})
    artifact_id = row.get("artifact_id") or result_payload.get("id")
    if artifact_id and "download_urls" not in result_payload:
        result_payload["download_urls"] = {
            output_format: f"/api/artifacts/{artifact_id}/download?format={output_format}"
            for output_format in result_payload.get(
                "requested_formats", ["docx", "pdf"]
            )
        }
    return {
        "id": row.get("id"),
        "status": row.get("status"),
        "stage": row.get("stage"),
        "progress": int(row.get("progress") or 0),
        "progress_details": row.get("progress_details") or {},
        "artifact_id": artifact_id,
        "result": result_payload,
        "attempt": int(row.get("attempt") or 0),
        "max_attempts": int(row.get("max_attempts") or 3),
        "heartbeat_at": row.get("heartbeat_at"),
        "recovery_count": int(row.get("recovery_count") or 0),
        "error": (
            {
                "code": row.get("error_code") or "ARTIFACT_GENERATION_FAILED",
                "message": row.get("error_message") or "成果生成失败",
            }
            if row.get("status") == "failed"
            else None
        ),
        "queued_at": row.get("queued_at"),
        "started_at": row.get("started_at"),
        "completed_at": row.get("completed_at"),
        "updated_at": row.get("updated_at"),
    }


async def load_job(
    db: Any, *, organization_id: str, job_id: str
) -> dict[str, Any] | None:
    result = (
        await db.table("artifact_generation_jobs")
        .select("*")
        .eq("organization_id", organization_id)
        .eq("id", job_id)
        .maybe_single()
        .execute()
    )
    return dict(result.data) if result.data else None


async def create_job(
    db: Any,
    *,
    organization_id: str,
    user_id: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    clean_payload = dict(payload)
    request_key = build_request_key(
        organization_id=organization_id,
        user_id=user_id,
        payload=clean_payload,
    )
    existing = (
        await db.table("artifact_generation_jobs")
        .select("*")
        .eq("organization_id", organization_id)
        .eq("request_key", request_key)
        .maybe_single()
        .execute()
    )
    if existing.data:
        return dict(existing.data), False

    now = _now()
    result = (
        await db.table("artifact_generation_jobs")
        .insert(
            {
                "organization_id": organization_id,
                "created_by": user_id,
                "request_key": request_key,
                "status": "queued",
                "stage": "queued",
                "progress": 0,
                "request_payload": clean_payload,
                "queued_at": now,
                "updated_at": now,
            }
        )
        .execute()
    )
    return dict((result.data or [{}])[0]), True


async def attach_task_id(db: Any, *, job_id: str, task_id: str) -> None:
    await db.table("artifact_generation_jobs").update(
        {"celery_task_id": task_id, "updated_at": _now()}
    ).eq("id", job_id).execute()


async def request_cancel(
    db: Any, *, organization_id: str, job_id: str
) -> dict[str, Any] | None:
    row = await load_job(db, organization_id=organization_id, job_id=job_id)
    if not row or row.get("status") in TERMINAL_JOB_STATUSES:
        return row
    next_status = "cancelled" if row.get("status") == "queued" else "cancelling"
    result = (
        await db.table("artifact_generation_jobs")
        .update(
            {
                "status": next_status,
                "stage": (
                    "cancelled" if next_status == "cancelled" else row.get("stage")
                ),
                "completed_at": _now() if next_status == "cancelled" else None,
                "updated_at": _now(),
            }
        )
        .eq("organization_id", organization_id)
        .eq("id", job_id)
        .execute()
    )
    return dict((result.data or [row])[0])


async def reset_for_retry(
    db: Any, *, organization_id: str, job_id: str
) -> dict[str, Any] | None:
    row = await load_job(db, organization_id=organization_id, job_id=job_id)
    if not row or row.get("status") != "failed":
        return row
    if int(row.get("attempt") or 0) >= int(row.get("max_attempts") or 3):
        return row
    result = (
        await db.table("artifact_generation_jobs")
        .update(
            {
                "status": "queued",
                "stage": "queued",
                "progress": 0,
                "progress_details": {},
                "result_payload": {},
                "artifact_id": None,
                "celery_task_id": None,
                "error_code": None,
                "error_message": None,
                "queued_at": _now(),
                "started_at": None,
                "completed_at": None,
                "lease_token": None,
                "lease_expires_at": None,
                "heartbeat_at": None,
                "worker_id": None,
                "updated_at": _now(),
            }
        )
        .eq("organization_id", organization_id)
        .eq("id", job_id)
        .execute()
    )
    return dict((result.data or [row])[0])


def _first_row(data: Any) -> dict[str, Any] | None:
    if isinstance(data, list):
        return dict(data[0]) if data else None
    return dict(data) if isinstance(data, dict) and data else None


async def _claim_job(db: Any, job_id: str) -> dict[str, Any] | None:
    worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
    result = await db.rpc(
        "claim_artifact_generation_job",
        {
            "p_job_id": job_id,
            "p_worker_id": worker_id,
            "p_lease_seconds": LEASE_SECONDS,
        },
    ).execute()
    return _first_row(result.data)


async def _heartbeat_loop(db: Any, *, job_id: str, lease_token: str) -> None:
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            await (
                db.table("artifact_generation_jobs")
                .update(
                    {
                        "heartbeat_at": _now(),
                        "lease_expires_at": (
                            datetime.now(UTC) + timedelta(seconds=LEASE_SECONDS)
                        ).isoformat(),
                        "updated_at": _now(),
                    }
                )
                .eq("id", job_id)
                .eq("lease_token", lease_token)
                .eq("status", "running")
                .execute()
            )
    except asyncio.CancelledError:
        raise


async def recover_stale_generation_jobs() -> dict[str, int]:
    """Recover expired leases and enqueue exactly the rows returned by SQL."""

    from app.core.database import supabase

    if not supabase:
        return {"recovered": 0, "requeued": 0, "failed": 0, "cancelled": 0}
    result = await supabase.rpc("recover_stale_artifact_generation_jobs", {}).execute()
    rows = result.data if isinstance(result.data, list) else []
    counters = {"recovered": len(rows), "requeued": 0, "failed": 0, "cancelled": 0}
    for row in rows:
        status = str(row.get("status") or "")
        if status == "queued":
            counters["requeued"] += 1
            try:
                task_id = enqueue_generation_job(str(row["id"]))
                await attach_task_id(supabase, job_id=str(row["id"]), task_id=task_id)
            except Exception as exc:  # broad-except: recovery must continue
                logger.warning(
                    "[ArtifactJob] failed to requeue %s: %s", row.get("id"), exc
                )
        elif status in counters:
            counters[status] += 1
    return counters


async def artifact_job_health(db: Any, *, organization_id: str) -> dict[str, Any]:
    result = (
        await db.table("artifact_generation_jobs")
        .select("status,stage,lease_expires_at,heartbeat_at,recovery_count,updated_at")
        .eq("organization_id", organization_id)
        .order("updated_at", desc=True)
        .limit(500)
        .execute()
    )
    rows = result.data or []
    counts: dict[str, int] = {}
    stale = 0
    now = datetime.now(UTC)
    for row in rows:
        status = str(row.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
        expires = row.get("lease_expires_at")
        if status == "running" and expires:
            try:
                stale += int(
                    datetime.fromisoformat(str(expires).replace("Z", "+00:00")) < now
                )
            except ValueError:
                stale += 1
    return {
        "sample_size": len(rows),
        "by_status": counts,
        "stale_running": stale,
        "recoveries": sum(int(row.get("recovery_count") or 0) for row in rows),
        "healthy": stale == 0,
    }


async def run_generation_job(job_id: str) -> dict[str, Any]:
    """Execute one job using the service client inside a worker or fallback task."""

    from app.core.database import supabase

    if not supabase:
        raise RuntimeError("Database is not configured")
    row = await _claim_job(supabase, job_id)
    if not row:
        result = (
            await supabase.table("artifact_generation_jobs")
            .select("*")
            .eq("id", job_id)
            .maybe_single()
            .execute()
        )
        row = dict(result.data or {})
    if not row:
        raise RuntimeError(f"Artifact generation job {job_id} not found")
    if not row.get("lease_token"):
        return public_job(row)

    organization_id = str(row["organization_id"])
    user_id = str(row.get("created_by") or "system")
    payload = dict(row.get("request_payload") or {})
    lease_token = str(row["lease_token"])
    heartbeat_task = asyncio.create_task(
        _heartbeat_loop(supabase, job_id=job_id, lease_token=lease_token)
    )

    async def progress_callback(
        stage: str, progress: int, details: dict[str, Any]
    ) -> None:
        state_result = (
            await supabase.table("artifact_generation_jobs")
            .select("status,lease_token")
            .eq("id", job_id)
            .maybe_single()
            .execute()
        )
        status = (state_result.data or {}).get("status")
        current_lease = str((state_result.data or {}).get("lease_token") or "")
        if current_lease != lease_token:
            raise ArtifactJobLeaseLostError("Artifact generation lease was reassigned")
        if status in {"cancelling", "cancelled"}:
            raise ArtifactGenerationCancelledError("Artifact generation was cancelled")
        await supabase.table("artifact_generation_jobs").update(
            {
                "stage": stage,
                "progress": progress,
                "progress_details": details,
                "updated_at": _now(),
            }
        ).eq("id", job_id).eq("lease_token", lease_token).execute()

    try:
        generated = await generate_artifact(
            db=supabase,
            organization_id=organization_id,
            user_id=user_id,
            original_request=str(payload.get("original_request") or ""),
            source_content=str(payload.get("source_content") or ""),
            title=payload.get("title"),
            artifact_type=ArtifactType(
                payload.get("artifact_type") or ArtifactType.CUSTOMER_SOLUTION.value
            ),
            audience=ArtifactAudience(
                payload.get("audience") or ArtifactAudience.CUSTOMER.value
            ),
            requested_formats=list(payload.get("requested_formats") or ["docx", "pdf"]),
            customer_context=dict(payload.get("customer_context") or {}),
            selected_document_ids=[
                str(item) for item in (payload.get("selected_document_ids") or [])
            ],
            target_character_count=payload.get("target_character_count"),
            generation_mode=str(payload.get("generation_mode") or "deep"),
            session_id=payload.get("session_id"),
            review_confirmed=bool(payload.get("review_confirmed")),
            progress_callback=progress_callback,
        )
        completed = (
            await supabase.table("artifact_generation_jobs")
            .update(
                {
                    "status": "completed",
                    "stage": "completed",
                    "progress": 100,
                    "result_payload": generated,
                    "artifact_id": generated.get("id"),
                    "completed_at": _now(),
                    "lease_token": None,
                    "lease_expires_at": None,
                    "worker_id": None,
                    "updated_at": _now(),
                }
            )
            .eq("id", job_id)
            .eq("lease_token", lease_token)
            .execute()
        )
        completed_row = _first_row(completed.data)
        if not completed_row:
            raise ArtifactJobLeaseLostError(
                "Artifact generation lease expired before commit"
            )
        try:
            await supabase.table("organization_activation_state").upsert(
                {
                    "organization_id": organization_id,
                    "step": "complete",
                    "first_outcome": (
                        "tender"
                        if payload.get("artifact_type") == "tender"
                        else "solution"
                    ),
                    "first_artifact_id": generated.get("id"),
                    "facts_confirmed": bool(payload.get("review_confirmed")),
                    "completed_at": _now(),
                    "updated_by": user_id,
                    "updated_at": _now(),
                },
                on_conflict="organization_id",
            ).execute()
        except Exception as exc:  # broad-except: intentional
            logger.info("[ArtifactJob] activation write-back skipped: %s", exc)
        from app.services.artifact_feedback_loop import record_delivery_event

        await record_delivery_event(
            supabase,
            organization_id=organization_id,
            artifact_id=str(generated.get("id") or ""),
            user_id=user_id,
            event_type="generated",
            metadata={"source": "durable-job", "job_id": job_id},
        )
        return public_job(completed_row)
    except ArtifactJobLeaseLostError:
        logger.warning("[ArtifactJob] worker lost lease job_id=%s", job_id)
        latest = (
            await supabase.table("artifact_generation_jobs")
            .select("*")
            .eq("id", job_id)
            .maybe_single()
            .execute()
        )
        return public_job(dict(latest.data or row))
    except ArtifactGenerationCancelledError:
        cancelled = (
            await supabase.table("artifact_generation_jobs")
            .update(
                {
                    "status": "cancelled",
                    "stage": "cancelled",
                    "completed_at": _now(),
                    "lease_token": None,
                    "lease_expires_at": None,
                    "worker_id": None,
                    "updated_at": _now(),
                }
            )
            .eq("id", job_id)
            .eq("lease_token", lease_token)
            .execute()
        )
        return public_job(_first_row(cancelled.data) or row)
    except Exception as exc:
        logger.exception("[ArtifactJob] generation failed job_id=%s", job_id)
        failed = (
            await supabase.table("artifact_generation_jobs")
            .update(
                {
                    "status": "failed",
                    "stage": "failed",
                    "error_code": type(exc).__name__[:100],
                    "error_message": str(exc)[:2000],
                    "completed_at": _now(),
                    "lease_token": None,
                    "lease_expires_at": None,
                    "worker_id": None,
                    "updated_at": _now(),
                }
            )
            .eq("id", job_id)
            .eq("lease_token", lease_token)
            .execute()
        )
        return public_job(_first_row(failed.data) or row)
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # progress and commit checks remain authoritative
            logger.warning("[ArtifactJob] heartbeat stopped job_id=%s: %s", job_id, exc)


def enqueue_generation_job(job_id: str) -> str:
    from app.tasks.artifact_tasks import generate_artifact_job

    task = generate_artifact_job.apply_async(args=[job_id], queue="artifacts")
    return str(task.id)
