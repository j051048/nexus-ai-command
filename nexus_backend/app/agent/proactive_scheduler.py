"""
P0-1: 后台任务调度器 - 让 Agent 主动工作

核心功能:
1. 定时触发 Agent 执行任务
2. 支持 Cron 表达式
3. 任务结果通知用户
"""

import asyncio
import logging
from datetime import datetime

from croniter import croniter

from app.core.database import supabase
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)


class ProactiveScheduler:
    """后台任务调度器"""

    def __init__(self):
        self.running_tasks: dict[str, asyncio.Task] = {}

    async def schedule_task(self, task_config: dict) -> str:
        """
        创建定时任务

        Args:
            task_config: {
                "name": "每日销售汇总",
                "cron": "0 9 * * *",  # 每天 9 点
                "prompt": "汇总昨日销售数据",
                "user_id": "uuid",
                "org_id": "uuid",
                "enabled": true
            }
        """
        cron_expression = task_config["cron"]
        next_execution_at = croniter(cron_expression, datetime.now()).get_next(datetime)
        # Persist in the single durable scheduler table. Celery Beat polls this
        # table, so API replicas never own long-lived cron loops.
        result = (
            await supabase.table("user_scheduled_tasks")
            .insert(
                {
                    "name": task_config["name"],
                    "cron_expression": cron_expression,
                    "prompt": task_config["prompt"],
                    "schedule_type": "cron",
                    "user_id": task_config["user_id"],
                    "organization_id": task_config.get("org_id"),
                    "is_active": task_config.get("enabled", True),
                    "next_execution_at": next_execution_at.isoformat(),
                    "created_at": datetime.utcnow().isoformat(),
                }
            )
            .execute()
        )

        task_id = result.data[0]["id"]

        return task_id

    async def start_task(self, task_id: str, config: dict):
        """启动后台任务"""
        if task_id in self.running_tasks:
            return

        task = asyncio.create_task(self._run_scheduled_task(task_id, config))
        self.running_tasks[task_id] = task

    async def _run_scheduled_task(self, task_id: str, config: dict):
        """执行定时任务循环"""
        cron = croniter(config["cron"], datetime.now())

        while True:
            try:
                # 计算下次执行时间
                next_run = cron.get_next(datetime)
                wait_seconds = (next_run - datetime.now()).total_seconds()

                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)

                # 执行任务
                await self._execute_task(task_id, config)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduled task {task_id} error: {e}")
                await asyncio.sleep(60)  # 错误后等待 1 分钟

    async def _execute_task(self, task_id: str, config: dict):
        """执行单次任务"""
        try:
            # 触发 Agent 执行
            chat_service = ChatService()
            result = await chat_service.send_message(
                user_id=config["user_id"],
                org_id=config.get("org_id"),
                message=config["prompt"],
                session_id=f"scheduled_{task_id}",
            )

            # 记录执行历史
            await supabase.table("agent_task_executions").insert(
                {
                    "task_id": task_id,
                    "executed_at": datetime.utcnow().isoformat(),
                    "status": "success",
                    "result_summary": result.get("response", "")[:500],
                }
            ).execute()

            logger.info(f"Scheduled task {task_id} executed successfully")

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            await supabase.table("agent_task_executions").insert(
                {
                    "task_id": task_id,
                    "executed_at": datetime.utcnow().isoformat(),
                    "status": "failed",
                    "error_message": str(e),
                }
            ).execute()

    async def stop_task(
        self, task_id: str, user_id: str | None = None, org_id: str | None = None
    ):
        """停止任务"""
        query = (
            supabase.table("user_scheduled_tasks")
            .update({"is_active": False})
            .eq("id", task_id)
        )
        if user_id:
            query = query.eq("user_id", user_id)
        if org_id:
            query = query.eq("organization_id", org_id)
        await query.execute()
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            del self.running_tasks[task_id]

    async def load_all_tasks(self):
        """Legacy single-instance mode only; production uses Celery polling."""
        logger.warning("Loading legacy in-process proactive system tasks")
        self._start_system_tasks()

    def _start_system_tasks(self):
        """启动系统级后台任务"""
        # 审批超时扫描
        task_id = "sys_approval_timeout_scan"
        if task_id not in self.running_tasks:
            self.running_tasks[task_id] = asyncio.create_task(
                self._scan_approval_timeouts_loop()
            )

        # ── 主动推送任务 ──────────────────────────────────────────────
        _SYSTEM_PUSH_TASKS = [
            {
                "id": "sys_daily_briefing",
                "cron": "0 9 * * *",  # 每日 9:00
                "prompt": (
                    "请生成今日工作简报，包括：待处理审批数量、今日到期合同、"
                    "重点客户跟进提醒、昨日关键数据变化。简洁输出，突出需要关注的事项。"
                ),
                "name": "每日工作简报",
            },
            {
                "id": "sys_customer_followup",
                "cron": "0 15 * * *",  # 每日 15:00
                "prompt": (
                    "检查最近 3 天没有跟进记录的客户，列出客户名称和上次跟进时间，"
                    "并给出简短的跟进建议。如果没有需要跟进的客户，回复'所有客户跟进状态良好'。"
                ),
                "name": "客户跟进提醒",
            },
            {
                "id": "sys_weekly_contract_expiry",
                "cron": "0 9 * * 1",  # 每周一 9:00
                "prompt": (
                    "检查本周即将到期的合同（7天内），列出合同名称、客户、到期日期和金额。"
                    "如果没有即将到期的合同，回复'本周无合同到期'。"
                ),
                "name": "合同到期预警",
            },
        ]

        for task_def in _SYSTEM_PUSH_TASKS:
            tid = task_def["id"]
            if tid not in self.running_tasks:
                self.running_tasks[tid] = asyncio.create_task(
                    self._run_system_push_loop(task_def)
                )
                logger.info(
                    f"Started system push task: {task_def['name']} ({task_def['cron']})"
                )

        # 缓存预热任务（每日凌晨 3:00）
        warmup_id = "sys_cache_warmup"
        if warmup_id not in self.running_tasks:
            self.running_tasks[warmup_id] = asyncio.create_task(
                self._cache_warmup_loop()
            )
            logger.info("Started system cache warmup task (daily 03:00)")

    async def _cache_warmup_loop(self):
        """每日凌晨预热语义缓存"""
        cron = croniter("0 3 * * *", datetime.now())
        while True:
            try:
                next_run = cron.get_next(datetime)
                wait_seconds = (next_run - datetime.now()).total_seconds()
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)

                from app.services.semantic_cache import semantic_cache_service

                await semantic_cache_service.warmup_common_queries()
                await semantic_cache_service.auto_warmup_from_history()
                logger.info("[CacheWarmup] Daily warmup completed")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[CacheWarmup] Error: {e}")
                await asyncio.sleep(300)

    async def _run_system_push_loop(self, task_def: dict):
        """运行系统级主动推送任务循环"""
        cron = croniter(task_def["cron"], datetime.now())

        while True:
            try:
                next_run = cron.get_next(datetime)
                wait_seconds = (next_run - datetime.now()).total_seconds()
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)

                # 获取所有活跃组织的 boss/founder 用户来推送
                await self._execute_system_push(task_def)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"System push task {task_def['id']} error: {e}")
                await asyncio.sleep(300)

    async def _execute_system_push(self, task_def: dict):
        """对所有活跃组织执行系统推送"""
        try:
            # 获取有活跃用户的组织
            result = (
                await supabase.table("users")
                .select("id, org_id, role")
                .in_("role", ["boss", "founder", "manager"])
                .limit(50)
                .execute()
            )

            if not result.data:
                return

            # 按 org_id 去重，每个组织只推送给第一个 boss/founder
            seen_orgs: set[str] = set()
            for user in result.data:
                org_id = user.get("org_id")
                if not org_id:
                    continue
                if org_id in seen_orgs:
                    continue
                seen_orgs.add(org_id)

                try:
                    chat_service = ChatService()
                    await chat_service.send_message(
                        user_id=user["id"],
                        org_id=org_id,
                        message=task_def["prompt"],
                        session_id=f"sys_push_{task_def['id']}",
                    )
                    logger.info(
                        f"System push '{task_def['name']}' sent to user {user['id'][:8]}... (org: {org_id[:8]}...)"
                    )
                except Exception as e:
                    logger.warning(
                        f"System push to user {user['id'][:8]}... failed: {e}"
                    )

        except Exception as e:
            logger.error(f"System push execution error: {e}")

    async def _scan_approval_timeouts_loop(self):
        """周期性扫描审批超时任务"""
        from app.core.database import supabase
        from app.services.approval_service import ApprovalService

        logger.info("Started system approval timeout scan loop.")
        while True:
            try:
                # 每 15 分钟执行一次扫描
                client = supabase
                if client:
                    escalated = await ApprovalService.check_approval_timeouts(client)
                    if escalated:
                        logger.info(
                            f"System scan escalated {len(escalated)} stalled approvals."
                        )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Approval timeout scan error: {e}")

            await asyncio.sleep(900)  # 15分钟


# 全局实例
proactive_scheduler = ProactiveScheduler()
