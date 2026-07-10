"""Durable execution engine for user-defined scheduled tasks.

Celery Beat is the authoritative poller. The optional in-process loop exists
only as an explicit legacy fallback. Due rows are claimed by a PostgreSQL RPC
using ``FOR UPDATE SKIP LOCKED`` so multiple workers cannot execute one task.
"""

import asyncio
import contextlib
import logging
import os
import socket
import time
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

CN_TZ = timezone(timedelta(hours=8))

# Unique instance identifier for distributed locking
_INSTANCE_ID = f"{socket.gethostname()}-{os.getpid()}"


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
        logger.info(
            "[ScheduledTaskRunner] Started (interval=%ds, instance=%s)",
            self._check_interval,
            _INSTANCE_ID,
        )

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("[ScheduledTaskRunner] Stopped")

    async def run_once(self) -> None:
        """Claim and execute one batch; used by the authoritative Celery poller."""
        await self._check_and_execute()

    async def _loop(self):
        # Wait a short while after startup to let DB connections stabilize
        await asyncio.sleep(10)

        self._last_system_task_date: str | None = None  # track daily execution
        consecutive_errors = 0

        while self._running:
            try:
                await self._check_and_execute()
                await self._maybe_run_system_tasks()
                consecutive_errors = 0
            except asyncio.CancelledError:
                break
            except Exception as e:
                consecutive_errors += 1
                msg = str(e)
                # Supabase transient 502/503 — log short summary, not the full HTML
                if any(code in msg for code in ("502", "503", "Bad gateway")):
                    logger.warning(
                        "[ScheduledTaskRunner] Supabase transient error (attempt %d): %s",
                        consecutive_errors,
                        msg[:120],
                    )
                else:
                    logger.error(
                        "[ScheduledTaskRunner] Loop error: %s", e, exc_info=True
                    )

            # Exponential backoff on consecutive failures (cap at 5 min)
            backoff = min(self._check_interval * (2 ** min(consecutive_errors, 3)), 300)
            await asyncio.sleep(backoff)

    async def _maybe_run_system_tasks(self):
        """Run system-level tasks once per day at ~09:00 CN time."""
        now_cn = datetime.now(CN_TZ)
        today_str = now_cn.strftime("%Y-%m-%d")

        # Already ran today
        if self._last_system_task_date == today_str:
            return

        # Only trigger after 09:00 CN
        if now_cn.hour < 9:
            return

        self._last_system_task_date = today_str

        try:
            from app.services.system_tasks import run_all_system_tasks

            await run_all_system_tasks()
        except Exception as e:
            logger.error(
                "[ScheduledTaskRunner] System tasks failed: %s", e, exc_info=True
            )

    async def _check_and_execute(self):
        from app.core.database import supabase

        if not supabase:
            return

        now = datetime.now(CN_TZ)
        now_iso = now.isoformat()

        # The RPC claims only the returned rows in one transaction. A fixed
        # five-row batch keeps the 15-minute stale-lock lease conservative even
        # when every Agent run consumes its full timeout.
        result = await supabase.rpc(
            "claim_due_user_scheduled_tasks",
            {
                "p_worker_id": _INSTANCE_ID,
                "p_due_before": now_iso,
                "p_limit": 5,
            },
        ).execute()

        tasks = result.data or []
        if not tasks:
            return

        logger.info("[ScheduledTaskRunner] Claimed %d due task(s)", len(tasks))

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
                        "locked_by": None,
                        "locked_at": None,
                    }
                    if failures >= 3:
                        fail_update["is_active"] = False
                        logger.warning(
                            "[ScheduledTaskRunner] Task %s auto-disabled after %d consecutive failures",
                            task.get("id", "?"),
                            failures,
                        )
                    else:
                        # Backoff: push next_execution_at forward by failures*5 minutes
                        backoff_time = now + timedelta(minutes=failures * 5)
                        fail_update["next_execution_at"] = backoff_time.isoformat()
                    await supabase.table("user_scheduled_tasks").update(fail_update).eq(
                        "id", task["id"]
                    ).execute()

    async def _execute_single(self, task: dict, supabase, now: datetime):
        from app.agent.proactive_runner import run_proactive_agent
        from app.services.agent_result_pusher import push_agent_result

        task_id = task["id"]
        user_id = task["user_id"]
        task_name = task["name"]
        task_start = time.time()

        logger.info(
            "[ScheduledTaskRunner] Executing '%s' for user %s", task_name, user_id
        )

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
            metadata={
                "source": "scheduled_task",
                "task_name": task_name,
                "task_id": task_id,
            },
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
                task.get("cron_expression"),
            )

        # 5. Update task record and release lock
        update_data = {
            "last_executed_at": now.isoformat(),
            "execution_count": (task.get("execution_count", 0) or 0) + 1,
            "last_result": response[:1000],
            "consecutive_failures": 0,
            "last_error": None,
            "locked_by": None,
            "locked_at": None,
        }

        if task["schedule_type"] == "once":
            update_data["is_active"] = False
        elif next_exec:
            update_data["next_execution_at"] = next_exec

        await supabase.table("user_scheduled_tasks").update(update_data).eq(
            "id", task_id
        ).execute()

        duration_ms = int((time.time() - task_start) * 1000)
        logger.info(
            "[ScheduledTaskRunner] Completed '%s' for user %s (next: %s, %dms)",
            task_name,
            user_id,
            next_exec[:16] if next_exec else "done",
            duration_ms,
        )


scheduled_task_runner = ScheduledTaskRunner()
