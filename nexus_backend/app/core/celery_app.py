import os
from celery import Celery

# Get Redis URL from env or default to localhost
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Initialize Celery app
celery_app = Celery(
    "nexus_tasks", broker=REDIS_URL, backend=REDIS_URL, include=["app.tasks.scheduler"]
)

# Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
)

# Periodic Tasks (Beat)
celery_app.conf.beat_schedule = {
    "daily-arxiv-harvest": {
        "task": "app.tasks.scheduler.crawl_arxiv_leads",
        "schedule": 86400.0,  # Every 24 hours
    },
}
