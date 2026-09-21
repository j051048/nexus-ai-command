"""Celery entry point for data-retention enforcement."""

from __future__ import annotations

import asyncio

from app.core.celery_app import NexusTask, celery_app
from app.services.data_retention_service import enforce_data_retention


@celery_app.task(
    name="app.tasks.retention_tasks.enforce_data_retention",
    base=NexusTask,
    max_retries=0,
    soft_time_limit=780,
    time_limit=900,
)
def enforce_data_retention_task():
    return asyncio.run(enforce_data_retention())
