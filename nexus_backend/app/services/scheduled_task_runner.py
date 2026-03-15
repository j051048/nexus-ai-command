"""
In-process Scheduled Task Runner

Replaces Celery Beat for user_scheduled_tasks execution.
Runs as an asyncio background loop inside the FastAPI process,
checking every 60 seconds for due tasks.
"""

import asyncio
import contextlib
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

CN_TZ = timezone(timedelta(hours=8))


class ScheduledTaskRunner:
    """Async background runner for user-defined scheduled tasks."""

    def __init__(self, check_interval: int = 60):
        self._check_interval = check_interval
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("[ScheduledTaskRunner] Started (interval=%ds)", self._check_interval)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("[ScheduledTaskRunner] Stopped")

    async def _loop(self):
        # Wait a short while after startup to let DB connections stabilize
        await asyncio.sleep(10)

        while self._running:
            try:
                await self._check_and_execute()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[ScheduledTaskRunner] Loop error: %s", e, exc_info=True)

            await asyncio.sleep(self._check_interval)

    async def _check_and_execute(self):
        from app.core.database import supabase

        if not supabase:
            return

        now = datetime.now(CN_TZ)
        now_iso = now.isoformat()

        result = (
            await supabase.table("user_scheduled_tasks")
            .select("*")
            .eq("is_active", True)
            .lte("next_execution_at", now_iso)
            .or_("consecutive_failures.lt.3,consecutive_failures.is.null")
            .order("next_execution_at")
            .limit(20)
            .execute()
        )

        tasks = result.data or []
        if not tasks:
            return

        logger.info("[ScheduledTaskRunner] Found %d due task(s)", len(tasks))

        for task in tasks:
            try:
                await self._execute_single(task, supabase, now)
            except Exception as e:
                logger.error(
                    "[ScheduledTaskRunner] Task %s failed: %s",
                    task.get("id", "?"),
                    e,
                    exc_info=True,
                )
                # Record failure with backoff and auto-disable
                with contextlib.suppress(Exception):
                    failures = (task.get("consecutive_failures") or 0) + 1
                    fail_update: dict = {
                        "consecutive_failures": failures,
                        "last_error": str(e)[:500],
                        "last_result": f"执行失败: {str(e)[:200]}",
                    }
                    if failures >= 3:
                        fail_update["is_active"] = False
                        logger.warning(
                            "[ScheduledTaskRunner] Task %s auto-disabled after %d consecutive failures",
                            task.get("id", "?"), failures,
                        )
                    else:
                        # Backoff: push next_execution_at forward by failures*5 minutes
                        backoff_time = now + timedelta(minutes=failures * 5)
                        fail_update["next_execution_at"] = backoff_time.isoformat()
                    await (
                        supabase.table("user_scheduled_tasks")
                        .update(fail_update)
                        .eq("id", task["id"])
                        .execute()
                    )

    async def _execute_single(self, task: dict, supabase, now: datetime):
        from app.agent.proactive_runner import run_proactive_agent
        from app.services.agent_result_pusher import push_agent_result

        task_id = task["id"]
        user_id = task["user_id"]
        task_name = task["name"]

        logger.info("[ScheduledTaskRunner] Executing '%s' for user %s", task_name, user_id)

        # Run AI agent
        agent_result = await run_proactive_agent(
            prompt=task["prompt"],
            user_id=user_id,
            org_id=task.get("organization_id"),
            agent_name=f"scheduled_{task_id[:8]}",
            timeout=60.0,
        )

        response = agent_result.get("response", "任务执行完成，但未生成结果。")

        # Unified push: notification + WS + chat
        await push_agent_result(
            user_id=user_id,
            title=f"定时任务: {task_name}",
            message=response,
            metadata={"source": "scheduled_task", "task_name": task_name, "task_id": task_id},
            org_id=task.get("organization_id"),
        )

        # 4. Compute next execution time
        from app.tools.scheduled_task_tools import _compute_next_execution

        next_exec = None
        if task["schedule_type"] != "once":
            next_exec = _compute_next_execution(
                task["schedule_type"],
                task.get("hour"),
                task.get("minute", 0),
                task.get("day_of_week"),
                task.get("interval_minutes"),
                None,
            )

        # 5. Update task record
        update_data = {
            "last_executed_at": now.isoformat(),
            "execution_count": (task.get("execution_count", 0) or 0) + 1,
            "last_result": response[:1000],
            "consecutive_failures": 0,
            "last_error": None,
        }

        if task["schedule_type"] == "once":
            update_data["is_active"] = False
        elif next_exec:
            update_data["next_execution_at"] = next_exec

        await supabase.table("user_scheduled_tasks").update(update_data).eq("id", task_id).execute()

        logger.info(
            "[ScheduledTaskRunner] Completed '%s' for user %s (next: %s)",
            task_name,
            user_id,
            next_exec[:16] if next_exec else "done",
        )


scheduled_task_runner = ScheduledTaskRunner()
