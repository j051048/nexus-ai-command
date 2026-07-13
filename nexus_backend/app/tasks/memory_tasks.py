"""Celery consumers for durable memory persistence jobs."""

import asyncio

from app.core.celery_app import NexusTask, celery_app


async def _process(job_id: str | None) -> bool:
    from app.services.conversation_memory.jobs import (
        claim_memory_job,
        run_claimed_memory_job,
    )

    job = await claim_memory_job(job_id)
    if not job:
        return False
    await run_claimed_memory_job(job)
    return True


@celery_app.task(
    name="app.tasks.memory_tasks.process_memory_persistence_job",
    bind=True,
    base=NexusTask,
    max_retries=4,
    default_retry_delay=20,
)
def process_memory_persistence_job(self, job_id: str):
    try:
        return asyncio.run(_process(job_id))
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.memory_tasks.drain_memory_persistence_jobs",
    base=NexusTask,
)
def drain_memory_persistence_jobs(limit: int = 20):
    async def _drain() -> int:
        processed = 0
        for _ in range(limit):
            if not await _process(None):
                break
            processed += 1
        return processed

    return asyncio.run(_drain())
