"""Celery tasks for restart-safe enterprise-knowledge ingestion."""

from __future__ import annotations

import asyncio

from app.core.celery_app import NexusTask, celery_app
from app.services.knowledge_ingestion_service import (
    mark_ingestion_retry,
    process_stored_document,
    recover_stale_knowledge_ingestion,
)


@celery_app.task(
    name="app.tasks.knowledge_tasks.process_knowledge_document",
    bind=True,
    base=NexusTask,
    max_retries=2,
    soft_time_limit=840,
    time_limit=900,
)
def process_knowledge_document(self, document_id: str, organization_id: str):
    try:
        result = asyncio.run(process_stored_document(document_id, organization_id))
        if str(result.get("status") or "") != "success":
            raise RuntimeError(
                str(result.get("reason") or "Knowledge ingestion incomplete")
            )
        return result
    except Exception as exc:
        if self.request.retries < self.max_retries:
            asyncio.run(
                mark_ingestion_retry(
                    document_id,
                    organization_id,
                    error=str(exc),
                )
            )
            raise self.retry(
                exc=exc,
                countdown=min(120, 20 * (self.request.retries + 1)),
            )
        raise


@celery_app.task(
    name="app.tasks.knowledge_tasks.recover_stale_knowledge_documents",
    base=NexusTask,
    max_retries=0,
    soft_time_limit=90,
    time_limit=120,
)
def recover_stale_knowledge_documents():
    return asyncio.run(recover_stale_knowledge_ingestion())
