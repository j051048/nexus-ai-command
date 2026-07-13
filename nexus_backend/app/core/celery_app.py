import logging
import os

from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_WORKER_CONCURRENCY = int(os.getenv("CELERY_WORKER_CONCURRENCY", "4"))

# Initialize Celery app
celery_app = Celery(
    "nexus_tasks",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.scheduler",
        "app.tasks.event_sensors",
        "app.tasks.tool_tasks",
        "app.tasks.memory_tasks",
    ],
)

# Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    # Distributed safety: ack after execution, reject on worker crash
    task_acks_late=True,
    worker_reject_on_worker_lost=True,
    worker_max_tasks_per_child=1000,
    # P1-8: Global task timeout defaults (individual tasks can override)
    task_soft_time_limit=300,  # 5 min soft limit → SoftTimeLimitExceeded
    task_time_limit=600,  # 10 min hard kill
    task_default_queue="default",
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("agent_tools", Exchange("agent_tools"), routing_key="agent_tools"),
        Queue(
            "agent_tools_high_risk",
            Exchange("agent_tools_high_risk"),
            routing_key="agent_tools_high_risk",
        ),
        Queue("webhooks", Exchange("webhooks"), routing_key="webhooks"),
        Queue("sensors", Exchange("sensors"), routing_key="sensors"),
    ),
    task_routes={
        "execute_tool_isolated": {
            "queue": "agent_tools",
            "routing_key": "agent_tools",
        },
        "execute_tool_high_risk": {
            "queue": "agent_tools_high_risk",
            "routing_key": "agent_tools_high_risk",
        },
        "app.tasks.event_sensors.*": {
            "queue": "sensors",
            "routing_key": "sensors",
        },
        "app.tasks.webhooks.*": {
            "queue": "webhooks",
            "routing_key": "webhooks",
        },
    },
    worker_prefetch_multiplier=1,
    worker_concurrency=CELERY_WORKER_CONCURRENCY,
)


# ── NexusTask: base class with DLQ on_failure ────────────────────────────────
class NexusTask(celery_app.Task):
    """Base task class that writes to DLQ on final failure."""

    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        try:
            from app.tasks.dlq import write_dead_letter

            write_dead_letter(
                task_name=self.name,
                task_id=task_id,
                args=args,
                kwargs=kwargs,
                exception=str(exc),
                traceback=str(einfo) if einfo else "",
                retries=self.request.retries if self.request else 0,
                max_retries=self.max_retries or 0,
            )
        except Exception as dlq_err:
            logger.error("[NexusTask] DLQ write failed: %s", dlq_err)
        super().on_failure(exc, task_id, args, kwargs, einfo)


# ── Distributed Beat Lock ────────────────────────────────────────────────────
# Use Redis-based distributed lock so only one Beat instance runs across
# multiple deployments. Falls back to default scheduler if Redis unavailable.
try:
    import redis as _redis

    _r = _redis.from_url(REDIS_URL, socket_connect_timeout=3)
    _r.ping()
    _r.close()
    celery_app.conf.beat_scheduler = "app.core.beat_lock.BeatLockScheduler"
    logger.info("[Celery] Using distributed BeatLockScheduler")
except Exception:
    logger.info("[Celery] Redis unavailable for Beat lock, using default scheduler")

# Periodic Tasks (Beat)
celery_app.conf.beat_schedule = {
    "memory-persistence-outbox": {
        "task": "app.tasks.memory_tasks.drain_memory_persistence_jobs",
        "schedule": 60.0,
    },
    "user-scheduled-task-poller": {
        "task": "app.tasks.scheduler.execute_user_scheduled_tasks",
        "schedule": 60.0,
    },
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
    # user-scheduled-tasks: 已由 ScheduledTaskRunner 进程内循环调度，
    # 删除 Beat 条目避免双重调度导致任务重复执行
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
    # ── Memory consolidation ("sleep cycle") ──
    "memory-consolidation": {
        "task": "app.tasks.scheduler.consolidate_memories",
        "schedule": crontab(hour=3, minute=30),  # 凌晨3:30 (在 decay cleanup 之前)
    },
    # ── Memory: purge superseded old versions ──
    "memory-purge-superseded": {
        "task": "app.tasks.scheduler.purge_superseded_memories",
        "schedule": crontab(
            hour=3, minute=45
        ),  # 凌晨3:45 (在 consolidation 和 decay 之间)
    },
    # ── Memory importance re-evaluation ──
    "memory-importance-reeval": {
        "task": "app.tasks.scheduler.reevaluate_memory_importance",
        "schedule": crontab(hour=4, minute=30, day_of_week=0),  # 每周日4:30
    },
    # ── KG strength time decay ──
    "kg-strength-decay": {
        "task": "app.tasks.scheduler.decay_kg_strength",
        "schedule": crontab(hour=4, minute=15, day_of_week=3),  # 每周三4:15
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
    # ── P1-4: Lead scoring ──
    "lead-scoring": {
        "task": "app.tasks.scheduler.score_all_leads_task",
        "schedule": crontab(minute=15),  # 每小时:15
    },
    "ai-roi-aggregation": {
        "task": "app.tasks.scheduler.aggregate_ai_roi_daily",
        "schedule": crontab(hour=0, minute=30),  # 每天凌晨0:30
    },
    "promote-agent-failures-to-evals": {
        "task": "app.tasks.scheduler.promote_agent_failures_to_eval_cases",
        "schedule": crontab(hour=1, minute=10),
    },
}
