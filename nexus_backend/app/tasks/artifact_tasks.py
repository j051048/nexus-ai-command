"""Celery entry points for durable artifact delivery jobs."""

from __future__ import annotations

import asyncio

from app.core.celery_app import NexusTask, celery_app
from app.services.artifact_generation_job_service import run_generation_job


@celery_app.task(
    name="app.tasks.artifact_tasks.generate_artifact_job",
    bind=True,
    base=NexusTask,
    max_retries=0,
    soft_time_limit=840,
    time_limit=900,
)
def generate_artifact_job(self, job_id: str):
    return asyncio.run(run_generation_job(job_id))
