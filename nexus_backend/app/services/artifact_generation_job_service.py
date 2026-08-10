"""Durable orchestration for long-running artifact generation jobs."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.agent.artifact_contract import ArtifactAudience, ArtifactType
from app.services.artifact_generation_service import (
    ArtifactGenerationCancelledError,
    generate_artifact,
)

logger = logging.getLogger(__name__)

TERMINAL_JOB_STATUSES = {"cancelled", "completed", "failed"}


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
                "updated_at": _now(),
            }
        )
        .eq("organization_id", organization_id)
        .eq("id", job_id)
        .execute()
    )
    return dict((result.data or [row])[0])


async def run_generation_job(job_id: str) -> dict[str, Any]:
    """Execute one job using the service client inside a worker or fallback task."""

    from app.core.database import supabase

    if not supabase:
        raise RuntimeError("Database is not configured")
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
    if row.get("status") in {"cancelled", "completed"}:
        return public_job(row)

    organization_id = str(row["organization_id"])
    user_id = str(row.get("created_by") or "system")
    payload = dict(row.get("request_payload") or {})
    attempt = int(row.get("attempt") or 0) + 1
    await supabase.table("artifact_generation_jobs").update(
        {
            "status": "running",
            "stage": "starting",
            "progress": 2,
            "attempt": attempt,
            "started_at": row.get("started_at") or _now(),
            "error_code": None,
            "error_message": None,
            "updated_at": _now(),
        }
    ).eq("id", job_id).execute()

    async def progress_callback(
        stage: str, progress: int, details: dict[str, Any]
    ) -> None:
        state_result = (
            await supabase.table("artifact_generation_jobs")
            .select("status")
            .eq("id", job_id)
            .maybe_single()
            .execute()
        )
        status = (state_result.data or {}).get("status")
        if status in {"cancelling", "cancelled"}:
            raise ArtifactGenerationCancelledError("Artifact generation was cancelled")
        await supabase.table("artifact_generation_jobs").update(
            {
                "stage": stage,
                "progress": progress,
                "progress_details": details,
                "updated_at": _now(),
            }
        ).eq("id", job_id).execute()

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
                    "updated_at": _now(),
                }
            )
            .eq("id", job_id)
            .execute()
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
        return public_job(dict((completed.data or [{}])[0]))
    except ArtifactGenerationCancelledError:
        cancelled = (
            await supabase.table("artifact_generation_jobs")
            .update(
                {
                    "status": "cancelled",
                    "stage": "cancelled",
                    "completed_at": _now(),
                    "updated_at": _now(),
                }
            )
            .eq("id", job_id)
            .execute()
        )
        return public_job(dict((cancelled.data or [{}])[0]))
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
                    "updated_at": _now(),
                }
            )
            .eq("id", job_id)
            .execute()
        )
        return public_job(dict((failed.data or [{}])[0]))


def enqueue_generation_job(job_id: str) -> str:
    from app.tasks.artifact_tasks import generate_artifact_job

    task = generate_artifact_job.apply_async(args=[job_id], queue="artifacts")
    return str(task.id)
