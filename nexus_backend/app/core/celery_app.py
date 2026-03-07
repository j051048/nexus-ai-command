import os

from celery import Celery
from celery.schedules import crontab

# Get Redis URL from env or default to localhost
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Initialize Celery app
celery_app = Celery(
    "nexus_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks.scheduler", "app.tasks.event_sensors"],
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
    "knowledge-base-gc": {
        "task": "app.tasks.scheduler.cleanup_stale_embeddings",
        "schedule": crontab(hour=3, minute=0),  # 每天凌晨3点
    },
    "ai-quality-aggregation": {
        "task": "app.tasks.scheduler.aggregate_ai_quality_metrics",
        "schedule": crontab(hour=23, minute=55),  # 每天23:55聚合当日数据
    },
    # P0-2: Migrated from main.py asyncio.create_task loops to Celery Beat
    "tenant-monitoring": {
        "task": "app.tasks.scheduler.monitor_tenants",
        "schedule": 300.0,  # 每5分钟
    },
    "approval-timeout-check": {
        "task": "app.tasks.scheduler.check_approval_timeouts",
        "schedule": 300.0,  # 每5分钟
    },
    "im-platform-sync": {
        "task": "app.tasks.scheduler.sync_im_platforms",
        "schedule": 3600.0,  # 每小时
    },
    "user-scheduled-tasks": {
        "task": "app.tasks.scheduler.execute_user_scheduled_tasks",
        "schedule": 60.0,  # 每分钟检查用户自定义定时任务
    },
    # ── P0-1: Event Sensors (proactive anomaly detection) ──
    "sensor-sales-anomaly": {
        "task": "app.tasks.event_sensors.sensor_sales_anomaly",
        "schedule": crontab(hour=10, minute=30),  # 每天10:30
    },
    "sensor-followup-timeout": {
        "task": "app.tasks.event_sensors.sensor_followup_timeout",
        "schedule": crontab(minute=0, hour="8,12,16,20"),  # 每4小时
    },
    "sensor-contract-expiry-ladder": {
        "task": "app.tasks.event_sensors.sensor_contract_expiry_ladder",
        "schedule": crontab(hour=9, minute=0),  # 每天9:00
    },
    "sensor-approval-backlog": {
        "task": "app.tasks.event_sensors.sensor_approval_backlog",
        "schedule": 1800.0,  # 每30分钟
    },
    "sensor-target-progress": {
        "task": "app.tasks.event_sensors.sensor_target_progress",
        "schedule": crontab(hour=17, minute=0),  # 每天17:00
    },
    # ── P0-2: Memory decay cleanup ──
    "memory-decay-cleanup": {
        "task": "app.tasks.scheduler.cleanup_stale_memories",
        "schedule": crontab(hour=4, minute=0),  # 每天凌晨4:00
    },
    # ── P1-2: Action outcome measurement ──
    "action-outcome-measurement": {
        "task": "app.tasks.scheduler.measure_action_outcomes",
        "schedule": crontab(hour=6, minute=0),  # 每天早6:00
    },
    # ── P0: Smart recommendation push ──
    "push-smart-recommendations": {
        "task": "app.tasks.scheduler.push_smart_recommendations",
        "schedule": crontab(minute=0, hour="*/2"),  # 每2小时
    },
}
