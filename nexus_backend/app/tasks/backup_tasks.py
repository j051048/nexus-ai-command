"""Celery entry points for backup execution and expiry.

Before these tasks existed, ``backup_schedules`` was written by the API and
read by nobody: the UI offered "automatic backups" that never ran, and
``backup_records.expires_at`` never reclaimed anything.
"""

from __future__ import annotations

import asyncio

from app.core.celery_app import NexusTask, celery_app
from app.services.backup_lifecycle import (
    expire_expired_backups,
    run_due_backup_schedules,
)


@celery_app.task(
    name="app.tasks.backup_tasks.run_due_backup_schedules",
    bind=True,
    base=NexusTask,
    max_retries=0,
    soft_time_limit=780,
    time_limit=900,
)
def run_due_backup_schedules_task(self):
    return asyncio.run(run_due_backup_schedules())


@celery_app.task(
    name="app.tasks.backup_tasks.expire_backup_records",
    base=NexusTask,
    max_retries=0,
    soft_time_limit=180,
    time_limit=240,
)
def expire_backup_records():
    return asyncio.run(expire_expired_backups())
