"""
P0 主动性功能 API 路由
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.agent.event_triggers import event_trigger
from app.agent.goal_tracker import goal_tracker
from app.agent.proactive_scheduler import proactive_scheduler
from app.core.auth import get_current_user_id
from app.core.errors import api_success

router = APIRouter(prefix="/api/agent/proactive", tags=["agent-proactive"])


# ===== 定时任务 =====

class ScheduleTaskRequest(BaseModel):
    name: str
    cron: str
    prompt: str
    enabled: bool = True


@router.post("/tasks")
async def create_scheduled_task(
    req: ScheduleTaskRequest,
    user_id: str = Depends(get_current_user_id)
):
    """创建定时任务"""
    task_id = await proactive_scheduler.schedule_task({
        "name": req.name,
        "cron": req.cron,
        "prompt": req.prompt,
        "user_id": user_id,
        "enabled": req.enabled
    })
    return api_success({"task_id": task_id}, "定时任务创建成功")


@router.delete("/tasks/{task_id}")
async def stop_scheduled_task(task_id: str):
    """停止定时任务"""
    await proactive_scheduler.stop_task(task_id)
    return api_success({}, "定时任务已停止")


# ===== 目标管理 =====

class CreateGoalRequest(BaseModel):
    goal_text: str
    deadline: str | None = None
    metadata: dict = {}


@router.post("/goals")
async def create_goal(
    req: CreateGoalRequest,
    user_id: str = Depends(get_current_user_id)
):
    """创建目标"""
    goal_id = await goal_tracker.create_goal({
        "user_id": user_id,
        "goal_text": req.goal_text,
        "deadline": req.deadline,
        "metadata": req.metadata
    })
    return api_success({"goal_id": goal_id}, "目标创建成功")


@router.get("/goals")
async def list_goals(user_id: str = Depends(get_current_user_id)):
    """获取活跃目标"""
    goals = await goal_tracker.get_active_goals(user_id)
    return api_success(goals)


@router.put("/goals/{goal_id}/progress")
async def update_goal_progress(goal_id: str, progress: dict):
    """更新目标进度"""
    await goal_tracker.update_progress(goal_id, progress)
    return api_success({}, "目标进度已更新")


@router.put("/goals/{goal_id}/complete")
async def complete_goal(goal_id: str):
    """完成目标"""
    await goal_tracker.complete_goal(goal_id)
    return api_success({}, "目标已完成")
