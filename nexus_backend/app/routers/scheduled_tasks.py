"""
Scheduled Tasks REST API

用户定时任务管理接口，支持 CRUD + 手动触发。
复用 user_scheduled_tasks 表和 scheduled_task_tools 中的调度计算逻辑。
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.database import supabase
from app.core.errors import ErrorCode, api_error, api_success
from app.tools.scheduled_task_tools import _compute_next_execution

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scheduled-tasks", tags=["Scheduled Tasks"])


def _get_admin_client():
    """Get the global service-key Supabase client (bypasses RLS)."""
    if not supabase:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")
    return supabase


# ─── Request Models ──────────────────────────────────────────


class CreateScheduledTaskBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="任务名称")
    prompt: str = Field(..., min_length=1, description="AI 执行此任务时的提示词")
    schedule_type: str = Field(..., description="调度类型: daily/weekly/once/interval")
    hour: int | None = Field(None, ge=0, le=23, description="执行时间-小时 (0-23)")
    minute: int = Field(0, ge=0, le=59, description="执行时间-分钟 (0-59)")
    day_of_week: int | None = Field(None, ge=0, le=6, description="星期几 (0=周一, 6=周日), 仅 weekly")
    interval_minutes: int | None = Field(None, ge=1, description="间隔分钟数, 仅 interval")
    notify_method: str = Field("notification", description="通知方式: notification/email")


class UpdateScheduledTaskBody(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    prompt: str | None = Field(None, min_length=1)
    schedule_type: str | None = None
    hour: int | None = Field(None, ge=0, le=23)
    minute: int | None = Field(None, ge=0, le=59)
    day_of_week: int | None = Field(None, ge=0, le=6)
    interval_minutes: int | None = Field(None, ge=1)
    is_active: bool | None = None
    notify_method: str | None = None


# ─── Endpoints ───────────────────────────────────────────────


@router.get("")
async def list_scheduled_tasks(
    include_inactive: bool = False,
    user_id: str = Depends(get_current_user_id),
):
    """获取当前用户的定时任务列表"""
    try:
        client = _get_admin_client()
        query = (
            client.table("user_scheduled_tasks")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(50)
        )
        if not include_inactive:
            query = query.eq("is_active", True)

        result = await query.execute()
        return api_success(data=result.data or [], message="定时任务列表获取成功")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error listing scheduled tasks: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "定时任务操作失败")


@router.post("")
async def create_scheduled_task(
    body: CreateScheduledTaskBody,
    user_id: str = Depends(get_current_user_id),
):
    """创建定时任务"""
    try:
        client = _get_admin_client()

        # 校验
        if body.schedule_type == "weekly" and body.day_of_week is None:
            raise api_error(ErrorCode.VALIDATION_ERROR, "每周任务需指定 day_of_week (0=周一, 6=周日)")
        if body.schedule_type == "interval" and not body.interval_minutes:
            raise api_error(ErrorCode.VALIDATION_ERROR, "间隔任务需指定 interval_minutes")
        if body.schedule_type in ("daily", "weekly", "once") and body.hour is None:
            raise api_error(ErrorCode.VALIDATION_ERROR, "daily/weekly/once 任务需指定 hour")

        # 限额检查
        existing = (
            await client.table("user_scheduled_tasks")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .execute()
        )
        if existing.count and existing.count >= 20:
            raise api_error(ErrorCode.VALIDATION_ERROR, "活跃定时任务已达上限 (20个)")

        next_exec = _compute_next_execution(
            body.schedule_type,
            body.hour,
            body.minute,
            body.day_of_week,
            body.interval_minutes,
            None,
        )

        task_data = {
            "user_id": user_id,
            "name": body.name,
            "prompt": body.prompt,
            "schedule_type": body.schedule_type,
            "hour": body.hour,
            "minute": body.minute,
            "day_of_week": body.day_of_week,
            "interval_minutes": body.interval_minutes,
            "is_active": True,
            "next_execution_at": next_exec,
            "notify_method": body.notify_method,
        }

        result = await client.table("user_scheduled_tasks").insert(task_data).execute()
        if not result.data:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "创建失败")

        return api_success(data=result.data[0], message="定时任务创建成功")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error creating scheduled task: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "定时任务操作失败")


@router.put("/{task_id}")
async def update_scheduled_task(
    task_id: str,
    body: UpdateScheduledTaskBody,
    user_id: str = Depends(get_current_user_id),
):
    """更新定时任务"""
    try:
        client = _get_admin_client()

        # 确认任务属于当前用户
        existing = (
            await client.table("user_scheduled_tasks")
            .select("*")
            .eq("id", task_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        if not existing.data:
            raise api_error(ErrorCode.NOT_FOUND, "定时任务不存在")

        task = existing.data
        update_data = {}

        for field_name in (
            "name",
            "prompt",
            "schedule_type",
            "hour",
            "minute",
            "day_of_week",
            "interval_minutes",
            "is_active",
            "notify_method",
        ):
            value = getattr(body, field_name, None)
            if value is not None:
                update_data[field_name] = value

        if not update_data:
            return api_success(data=task, message="无需更新")

        # 重新计算下次执行时间
        stype = update_data.get("schedule_type", task["schedule_type"])
        hour = update_data.get("hour", task.get("hour"))
        minute = update_data.get("minute", task.get("minute", 0))
        dow = update_data.get("day_of_week", task.get("day_of_week"))
        interval = update_data.get("interval_minutes", task.get("interval_minutes"))
        is_active = update_data.get("is_active", task.get("is_active", True))

        if is_active:
            update_data["next_execution_at"] = _compute_next_execution(
                stype,
                hour,
                minute,
                dow,
                interval,
                None,
            )

        update_data["update_time"] = datetime.now(UTC).isoformat()

        result = await client.table("user_scheduled_tasks").update(update_data).eq("id", task_id).execute()

        return api_success(data=result.data[0] if result.data else task, message="定时任务更新成功")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error updating scheduled task: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "定时任务操作失败")


@router.delete("/{task_id}")
async def delete_scheduled_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """删除定时任务"""
    try:
        client = _get_admin_client()

        # 确认任务属于当前用户
        existing = (
            await client.table("user_scheduled_tasks").select("id").eq("id", task_id).eq("user_id", user_id).execute()
        )
        if not existing.data:
            raise api_error(ErrorCode.NOT_FOUND, "定时任务不存在")

        await client.table("user_scheduled_tasks").delete().eq("id", task_id).execute()
        # 清理该任务产生的推送消息，防止登录/刷新时重复显示
        try:
            await (
                client.table("chat_messages")
                .delete()
                .eq("user_id", user_id)
                .filter("metadata->>task_id", "eq", task_id)
                .execute()
            )
        except Exception:
            pass  # 非关键路径，静默失败
        return api_success(data=None, message="定时任务已删除")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error deleting scheduled task: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "定时任务操作失败")


@router.post("/{task_id}/run")
async def run_scheduled_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """手动触发执行一次定时任务"""
    try:
        client = _get_admin_client()

        existing = (
            await client.table("user_scheduled_tasks")
            .select("*")
            .eq("id", task_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        if not existing.data:
            raise api_error(ErrorCode.NOT_FOUND, "定时任务不存在")

        task = existing.data

        # 调用 proactive_runner 异步执行
        try:
            import asyncio

            from app.agent.proactive_runner import run_proactive_agent

            asyncio.create_task(
                run_proactive_agent(
                    user_id=user_id,
                    prompt=task["prompt"],
                )
            )
        except Exception as run_err:
            logger.warning(f"Failed to trigger proactive agent: {run_err}")
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, f"触发执行失败: {run_err}")

        # 更新执行统计
        await (
            client.table("user_scheduled_tasks")
            .update(
                {
                    "last_executed_at": datetime.now(UTC).isoformat(),
                    "execution_count": (task.get("execution_count") or 0) + 1,
                }
            )
            .eq("id", task_id)
            .execute()
        )

        return api_success(data={"task_id": task_id}, message="任务已触发执行，结果将通过通知推送")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error running scheduled task: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "定时任务操作失败")
