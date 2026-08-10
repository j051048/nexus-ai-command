"""Durable source storage and retryable knowledge ingestion orchestration."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import httpx

from app.services.etl import etl_service

logger = logging.getLogger(__name__)

SOURCE_BUCKET = os.getenv("KNOWLEDGE_SOURCE_BUCKET", "documents")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _storage_config() -> tuple[str, str] | None:
    url = (os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_URI") or "").strip()
    key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    return (url.rstrip("/"), key) if url and key else None


def build_source_storage_path(
    *, organization_id: str, document_id: str, filename: str
) -> str:
    basename = (filename or "document").replace("\\", "/").rsplit("/", 1)[-1]
    safe_name = "".join(
        char if char.isalnum() or char in {".", "-", "_"} else "_" for char in basename
    )[-180:].lstrip(".")
    safe_name = safe_name.replace("..", "_")
    return (
        f"{organization_id}/knowledge/{document_id}/"
        f"{uuid4().hex[:12]}_{safe_name or 'document'}"
    )


async def _storage_request(
    method: str,
    storage_path: str,
    *,
    content: bytes | None = None,
    content_type: str = "application/octet-stream",
) -> bytes:
    config = _storage_config()
    if not config:
        raise RuntimeError("Supabase Storage is not configured")
    base_url, service_key = config
    encoded_path = quote(storage_path, safe="/")
    endpoint = f"{base_url}/storage/v1/object/{SOURCE_BUCKET}/{encoded_path}"
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
    }
    if content is not None:
        headers.update({"Content-Type": content_type, "x-upsert": "true"})
    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=15.0)) as client:
        response = await client.request(
            method, endpoint, headers=headers, content=content
        )
        response.raise_for_status()
        return response.content


async def persist_source_file(
    db: Any,
    *,
    organization_id: str,
    document_id: str,
    filename: str,
    content: bytes,
    content_type: str | None,
) -> str | None:
    """Persist original bytes. Returning ``None`` keeps legacy fallback usable."""
    storage_path = build_source_storage_path(
        organization_id=organization_id,
        document_id=document_id,
        filename=filename,
    )
    try:
        await _storage_request(
            "POST",
            storage_path,
            content=content,
            content_type=content_type or "application/octet-stream",
        )
        await (
            db.table("documents")
            .update(
                {
                    "source_storage_path": storage_path,
                    "source_content_type": content_type or "application/octet-stream",
                    "ingestion_updated_at": _now(),
                    "ingestion_error_code": None,
                }
            )
            .eq("organization_id", organization_id)
            .eq("id", document_id)
            .execute()
        )
        return storage_path
    except Exception as exc:  # broad-except: upload endpoint retains in-memory fallback
        logger.warning("[KnowledgeIngestion] source persistence unavailable: %s", exc)
        return None


async def process_stored_document(
    document_id: str, organization_id: str
) -> dict[str, Any]:
    from app.core.database import supabase

    if not supabase:
        raise RuntimeError("Database is not configured")
    result = (
        await supabase.table("documents")
        .select("*")
        .eq("organization_id", organization_id)
        .eq("id", document_id)
        .maybe_single()
        .execute()
    )
    document = dict(result.data or {})
    if not document:
        raise RuntimeError("Knowledge document does not exist")
    storage_path = str(document.get("source_storage_path") or "")
    if not storage_path:
        raise RuntimeError("Knowledge source file is not persisted")

    attempt = int(document.get("ingestion_attempt") or 0) + 1
    await (
        supabase.table("documents")
        .update(
            {
                "status": "processing",
                "stage": "queued",
                "progress": 2,
                "ingestion_attempt": attempt,
                "ingestion_updated_at": _now(),
                "ingestion_error_code": None,
                "error_log": None,
            }
        )
        .eq("organization_id", organization_id)
        .eq("id", document_id)
        .execute()
    )
    try:
        content = await _storage_request("GET", storage_path)
        outcome = await etl_service.process_file(
            content=content,
            filename=str(document.get("name") or "document"),
            doc_id=document_id,
            user_id=str(document.get("owner_id") or "system"),
            organization_id=organization_id,
            category=str(document.get("doc_type") or "other"),
        )
        success = str(outcome.get("status") or "") == "success"
        await (
            supabase.table("documents")
            .update(
                {
                    "ingestion_updated_at": _now(),
                    "ingestion_error_code": None if success else "INGESTION_INCOMPLETE",
                }
            )
            .eq("organization_id", organization_id)
            .eq("id", document_id)
            .execute()
        )
        return outcome
    except Exception as exc:
        logger.exception("[KnowledgeIngestion] failed document_id=%s", document_id)
        await (
            supabase.table("documents")
            .update(
                {
                    "status": "error",
                    "stage": "failed",
                    "ingestion_updated_at": _now(),
                    "ingestion_error_code": type(exc).__name__[:100],
                    "error_log": str(exc)[:500],
                }
            )
            .eq("organization_id", organization_id)
            .eq("id", document_id)
            .execute()
        )
        raise


async def mark_ingestion_retry(
    document_id: str,
    organization_id: str,
    *,
    error: str,
) -> None:
    from app.core.database import supabase

    if not supabase:
        return
    await (
        supabase.table("documents")
        .update(
            {
                "status": "pending",
                "stage": "retrying",
                "progress": 1,
                "ingestion_updated_at": _now(),
                "ingestion_error_code": "INGESTION_RETRY_SCHEDULED",
                "error_log": error[:500],
            }
        )
        .eq("organization_id", organization_id)
        .eq("id", document_id)
        .execute()
    )


def enqueue_knowledge_ingestion(document_id: str, organization_id: str) -> str:
    from app.tasks.knowledge_tasks import process_knowledge_document

    task = process_knowledge_document.apply_async(
        args=[document_id, organization_id], queue="knowledge"
    )
    return str(task.id)


async def recover_stale_knowledge_ingestion() -> dict[str, int]:
    """Atomically recover stalled rows, then enqueue only claimed documents."""

    from app.core.database import supabase

    if not supabase:
        return {"recovered": 0, "requeued": 0, "enqueue_failed": 0}
    result = await supabase.rpc(
        "recover_stale_knowledge_ingestion",
        {"p_stale_minutes": 15, "p_limit": 100},
    ).execute()
    rows = result.data if isinstance(result.data, list) else []
    counters = {"recovered": len(rows), "requeued": 0, "enqueue_failed": 0}
    for row in rows:
        try:
            enqueue_knowledge_ingestion(str(row["id"]), str(row["organization_id"]))
            counters["requeued"] += 1
        except Exception as exc:  # continue recovering independent documents
            counters["enqueue_failed"] += 1
            logger.warning(
                "[KnowledgeIngestion] failed to requeue document_id=%s: %s",
                row.get("id"),
                exc,
            )
    return counters


async def knowledge_ingestion_health(
    db: Any, *, organization_id: str
) -> dict[str, Any]:
    result = (
        await db.table("documents")
        .select("status,stage,progress,ingestion_attempt,ingestion_updated_at")
        .eq("organization_id", organization_id)
        .order("created_at", desc=True)
        .limit(500)
        .execute()
    )
    rows = result.data or []
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    failed = counts.get("failed", 0) + counts.get("error", 0)
    stale = 0
    now = datetime.now(UTC)
    for row in rows:
        if str(row.get("status") or "") not in {"pending", "processing"}:
            continue
        updated = row.get("ingestion_updated_at")
        if not updated:
            stale += 1
            continue
        try:
            timestamp = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
            stale += int((now - timestamp).total_seconds() > 15 * 60)
        except ValueError:
            stale += 1
    return {
        "sample_size": len(rows),
        "by_status": counts,
        "failed": failed,
        "processing": counts.get("pending", 0) + counts.get("processing", 0),
        "stale": stale,
        "ready": counts.get("ready", 0) + counts.get("completed", 0),
        "healthy": failed == 0 and stale == 0,
    }
