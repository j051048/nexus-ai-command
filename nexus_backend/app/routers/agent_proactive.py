"""
P0 主动性功能 API 路由
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.agent.goal_tracker import goal_tracker
from app.agent.proactive_scheduler import proactive_scheduler
from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent/proactive", tags=["agent-proactive"])


# ===== 定时任务 =====


class ScheduleTaskRequest(BaseModel):
    name: str
    cron: str
    prompt: str
    enabled: bool = True


@router.post("/tasks")
async def create_scheduled_task(req: ScheduleTaskRequest, user_id: str = Depends(get_current_user_id)):
    """创建定时任务"""
    try:
        task_id = await proactive_scheduler.schedule_task(
            {"name": req.name, "cron": req.cron, "prompt": req.prompt, "user_id": user_id, "enabled": req.enabled}
        )
        return api_success({"task_id": task_id}, "定时任务创建成功")
    except Exception as e:
        logger.error(f"Create scheduled task failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "创建定时任务失败")


@router.delete("/tasks/{task_id}")
async def stop_scheduled_task(task_id: str):
    """停止定时任务"""
    try:
        await proactive_scheduler.stop_task(task_id)
        return api_success({}, "定时任务已停止")
    except Exception as e:
        logger.error(f"Stop scheduled task failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "停止定时任务失败")


# ===== 目标管理 =====


class CreateGoalRequest(BaseModel):
    goal_text: str
    deadline: str | None = None
    metadata: dict = {}


@router.post("/goals")
async def create_goal(req: CreateGoalRequest, user_id: str = Depends(get_current_user_id)):
    """创建目标"""
    try:
        goal_id = await goal_tracker.create_goal(
            {"user_id": user_id, "goal_text": req.goal_text, "deadline": req.deadline, "metadata": req.metadata}
        )
        return api_success({"goal_id": goal_id}, "目标创建成功")
    except Exception as e:
        logger.error(f"Create goal failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "创建目标失败")


@router.get("/goals")
async def list_goals(user_id: str = Depends(get_current_user_id)):
    """获取活跃目标"""
    try:
        goals = await goal_tracker.get_active_goals(user_id)
        return api_success(goals)
    except Exception as e:
        logger.error(f"List goals failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取目标列表失败")


@router.put("/goals/{goal_id}/progress")
async def update_goal_progress(goal_id: str, progress: dict):
    """更新目标进度"""
    try:
        await goal_tracker.update_progress(goal_id, progress)
        return api_success({}, "目标进度已更新")
    except Exception as e:
        logger.error(f"Update goal progress failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "更新目标进度失败")


@router.put("/goals/{goal_id}/complete")
async def complete_goal(goal_id: str):
    """完成目标"""
    try:
        await goal_tracker.complete_goal(goal_id)
        return api_success({}, "目标已完成")
    except Exception as e:
        logger.error(f"Complete goal failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "完成目标失败")
