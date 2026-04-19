"""Application lifespan manager — startup and shutdown logic."""

import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""

    from app.services.audit_logger import audit_logger
    from app.services.cache_service import cache_service
    from app.services.event_bus import event_bus

    # Startup
    logger.info("Starting Nexus Backend...")

    from app.core.env_config import env_config

    env_errors = env_config.validate_all()
    if env_errors:
        for err in env_errors:
            logger.warning(f"Env config: {err}")
    else:
        logger.info("Environment configuration validated")

    await cache_service.init()
    await event_bus.start()
    logger.info("Event Bus started")

    # Initialize LangGraph checkpointer (for state persistence)
    from app.agent.checkpointer import setup_checkpointer

    try:
        await setup_checkpointer()
        logger.info("LangGraph Checkpointer initialized")
    except Exception as e:
        logger.warning(f"Checkpointer initialization skipped: {e}")

    # Cold start optimization: pre-compile LangGraph agent graph
    try:
        from app.agent.graph import warmup_agent_graph

        warmup_agent_graph()
        logger.info("LangGraph agent graph pre-compiled")
    except Exception as e:
        logger.warning(f"Agent graph warmup skipped: {e}")

    # Cold start optimization: Initialize connection pools
    from app.services.connection_pool_service import connection_pool_service

    try:
        await connection_pool_service.init_all()
        logger.info("Connection pools initialized")
    except Exception as e:
        logger.warning(f"Connection pool init skipped: {e}")

    # #20: 启动时验证关键表列是否存在
    from app.core.schema_validator import validate_schema

    try:
        schema_warnings = await validate_schema()
        if schema_warnings:
            logger.warning(f"Schema validation: {len(schema_warnings)} warnings")
    except Exception as e:
        logger.warning(f"Schema validation skipped: {e}")

    # P0-5: Startup assert — verify _get_client rejects calls without tenant context
    from app.tools._shared import _get_client

    try:
        _get_client({})
        logger.critical("[SECURITY] _get_client({}) did NOT raise — service_role leak!")
        raise SystemExit(1)
    except PermissionError:
        logger.info("Tenant isolation guard verified (_get_client rejects empty config)")
    except RuntimeError:
        # Database not configured — acceptable in test/CI
        logger.info("Tenant isolation guard: DB not configured (acceptable in CI)")

    # #18: 自动执行数据库迁移
    # Item 19: Production默认不执行迁移，使用CI/CD管线；开发环境保持自动
    _run_migrations = os.environ.get(
        "RUN_MIGRATIONS_ON_STARTUP",
        "false" if settings.IS_PRODUCTION else "true",
    ).lower() in ("true", "1", "yes")

    if _run_migrations:
        from app.core.migration_runner import run_migrations

        try:
            applied = await run_migrations()
            if applied:
                logger.info(f"Migration runner: {len(applied)} migrations processed")
        except Exception as e:
            logger.warning(f"Migration runner skipped: {e}")
    else:
        logger.info("Migrations skipped (production). Run via CI/CD pipeline.")

    # Warm up tiktoken encoders (prevents first-request latency)
    try:
        from app.services.token_service import token_counter

        token_counter.count_tokens("warmup", "gpt-4o")
        token_counter.count_tokens("warmup", "gpt-4o-mini")
        logger.info("Token encoders warmed up")
    except Exception as e:
        logger.warning(f"Tiktoken warmup skipped: {e}")

    # P0 #9: Pre-load jieba dictionary (prevents ~1s delay on first query)
    try:
        import jieba

        jieba.setLogLevel(40)  # WARNING level
        jieba.initialize()
        logger.info("Jieba dictionary pre-loaded")
    except ImportError:
        logger.debug("Jieba not installed, skipping pre-load")
    except Exception as e:
        logger.warning(f"Jieba pre-load skipped: {e}")

    # P0-2: Background tasks migrated to Celery Beat (see app/tasks/scheduler.py)
    # - monitor_tenants (every 5 min)
    # - check_approval_timeouts (every 5 min)
    # - sync_im_platforms (every hour)

    # Start auto-trigger service (3.2 主动监控)
    from app.services.auto_trigger_service import auto_trigger_service

    try:
        await auto_trigger_service.start()
        logger.info("Auto-trigger service started")
    except Exception as e:
        logger.warning(f"Auto-trigger service start skipped: {e}")

    # Start in-process scheduled task runner (replaces Celery Beat)
    from app.services.scheduled_task_runner import scheduled_task_runner

    try:
        await scheduled_task_runner.start()
        logger.info("Scheduled task runner started")
    except Exception as e:
        logger.warning(f"Scheduled task runner start skipped: {e}")

    # P0-1: Start proactive scheduler
    from app.agent.proactive_scheduler import proactive_scheduler

    try:
        await proactive_scheduler.load_all_tasks()
        logger.info("Proactive scheduler started")
    except Exception as e:
        logger.warning(f"Proactive scheduler start skipped: {e}")

    # P0-3: Register default event triggers
    from app.agent.event_triggers import register_default_triggers

    try:
        register_default_triggers()
        logger.info("Event triggers registered")
    except Exception as e:
        logger.warning(f"Event triggers registration skipped: {e}")

    # G6: Start background health checker (O(1) cached /health)
    from app.core.health_cache import health_cache

    try:
        health_cache.start_background_checker()
        logger.info("Health cache background checker started")
    except Exception as e:
        logger.warning(f"Health cache start skipped: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Nexus Backend...")
    with suppress(Exception):
        await health_cache.stop()
    with suppress(Exception):
        await scheduled_task_runner.stop()
    with suppress(Exception):
        # Stop all proactive scheduler tasks
        for task_id in list(proactive_scheduler.running_tasks.keys()):
            await proactive_scheduler.stop_task(task_id)
    with suppress(Exception):
        await auto_trigger_service.stop()
    await event_bus.stop()
    await audit_logger.force_flush()
    with suppress(Exception):
        await connection_pool_service.close()
    # P0 Fix: Gracefully close checkpointer connection pool
    with suppress(Exception):
        from app.agent.checkpointer import shutdown_checkpointer

        await shutdown_checkpointer()
    logger.info("Cleanup complete")
