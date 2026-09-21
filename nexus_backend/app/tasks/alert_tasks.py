"""Celery entry point for the SLO alerting sweep."""

from __future__ import annotations

import asyncio

from app.core.celery_app import NexusTask, celery_app
from app.services.slo_alert_service import evaluate_and_dispatch


@celery_app.task(
    name="app.tasks.alert_tasks.evaluate_slo_alerts",
    base=NexusTask,
    max_retries=0,
    soft_time_limit=240,
    time_limit=300,
)
def evaluate_slo_alerts():
    return asyncio.run(evaluate_and_dispatch())
