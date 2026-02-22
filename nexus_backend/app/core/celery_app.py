import os

from celery import Celery
from celery.schedules import crontab

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
    "morning-briefing": {
        "task": "app.tasks.scheduler.push_daily_briefing",
        "schedule": crontab(hour=8, minute=0),  # 每天早8点
    },
    "lead-mining": {
        "task": "app.tasks.scheduler.mine_sales_leads",
        "schedule": crontab(hour=10, minute=0),  # 每天上午10点
    },
    "competitor-monitor": {
        "task": "app.tasks.scheduler.monitor_competitors",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),  # 每周一早9点
    },
    "contract-expiry-check": {
        "task": "app.tasks.scheduler.check_contract_expiry",
        "schedule": crontab(hour=9, minute=30),  # 每天早9:30
    },
}
