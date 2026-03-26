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
from typing import Any
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
        # 保存到数据库
        result = await supabase.table("agent_scheduled_tasks").insert({
            "name": task_config["name"],
            "cron_expression": task_config["cron"],
            "prompt_template": task_config["prompt"],
            "user_id": task_config["user_id"],
            "org_id": task_config.get("org_id", "default"),
            "enabled": task_config.get("enabled", True),
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        task_id = result.data[0]["id"]

        # 启动后台任务
        if task_config.get("enabled", True):
            await self.start_task(task_id, task_config)

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
                org_id=config.get("org_id", "default"),
                message=config["prompt"],
                session_id=f"scheduled_{task_id}"
            )

            # 记录执行历史
            await supabase.table("agent_task_executions").insert({
                "task_id": task_id,
                "executed_at": datetime.utcnow().isoformat(),
                "status": "success",
                "result_summary": result.get("response", "")[:500]
            }).execute()

            logger.info(f"Scheduled task {task_id} executed successfully")

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            await supabase.table("agent_task_executions").insert({
                "task_id": task_id,
                "executed_at": datetime.utcnow().isoformat(),
                "status": "failed",
                "error_message": str(e)
            }).execute()

    async def stop_task(self, task_id: str):
        """停止任务"""
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            del self.running_tasks[task_id]

    async def load_all_tasks(self):
        """启动时加载所有启用的任务"""
        result = await supabase.table("agent_scheduled_tasks")\
            .select("*")\
            .eq("enabled", True)\
            .execute()

        for task in result.data:
            await self.start_task(task["id"], {
                "cron": task["cron_expression"],
                "prompt": task["prompt_template"],
                "user_id": task["user_id"],
                "org_id": task["org_id"]
            })


# 全局实例
proactive_scheduler = ProactiveScheduler()
