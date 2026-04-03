"""VMD 任务路由"""

import logging

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vmd/tasks", tags=["VMD Tasks"])


@router.get("")
async def list_vmd_tasks(
    req: Request,
    status: str | None = Query(None),
    priority: str | None = Query(None),
    user_id: str = Depends(get_current_user_id),
):
    """获取 VMD 任务列表，支持状态和优先级过滤"""
    db = getattr(req.state, "db", None)
    if not db:
        return api_success(data={"tasks": []})

    query = db.table("vmd_main_task").select("*").order("create_time", desc=True)

    if status:
        query = query.eq("status", status)
    if priority:
        query = query.eq("priority", priority)

    result = await query.execute()
    return api_success(data={"tasks": result.data or []})


@router.get("/{task_id}")
async def get_vmd_task_detail(req: Request, task_id: str, user_id: str = Depends(get_current_user_id)):
    """获取单个 VMD 任务详情"""
    db = getattr(req.state, "db", None)
    if not db:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, message="数据库连接未配置")

    # 支持 task_code 或 UUID
    column = "task_code" if not task_id.replace("-", "").isalnum() or len(task_id) < 20 else "id"
    result = await db.table("vmd_main_task").select("*").eq(column, task_id).maybe_single().execute()

    if not result.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, message="任务不存在")

    return api_success(data=result.data)


@router.post("/{task_id}/pause")
async def pause_vmd_task(req: Request, task_id: str, user_id: str = Depends(get_current_user_id)):
    """暂停 VMD 任务"""
    db = getattr(req.state, "db", None)
    if not db:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR)

    # 1. 检查任务是否存在及当前状态
    task = await db.table("vmd_main_task").select("status").eq("id", task_id).maybe_single().execute()
    if not task.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, message="任务不存在")

    if task.data["status"] != "running":
        raise api_error(ErrorCode.VMD_TASK_STATUS_INVALID, message="只有进行中的任务可以暂停")

    # 2. 更新状态
    await db.table("vmd_main_task").update({"status": "paused"}).eq("id", task_id).execute()
    return api_success(data={"status": "paused"}, message="任务已暂停")


@router.post("/{task_id}/resume")
async def resume_vmd_task(req: Request, task_id: str, user_id: str = Depends(get_current_user_id)):
    """恢复 VMD 任务"""
    db = getattr(req.state, "db", None)
    if not db:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR)

    task = await db.table("vmd_main_task").select("status").eq("id", task_id).maybe_single().execute()
    if not task.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, message="任务不存在")

    if task.data["status"] != "paused":
        raise api_error(ErrorCode.VMD_TASK_STATUS_INVALID, message="只有已暂停的任务可以恢复")

    await db.table("vmd_main_task").update({"status": "running"}).eq("id", task_id).execute()
    return api_success(data={"status": "running"}, message="任务已恢复")


@router.post("/{task_id}/cancel")
async def cancel_vmd_task(req: Request, task_id: str, user_id: str = Depends(get_current_user_id)):
    """取消 VMD 任务"""
    db = getattr(req.state, "db", None)
    if not db:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR)

    task = await db.table("vmd_main_task").select("status").eq("id", task_id).maybe_single().execute()
    if not task.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, message="任务不存在")

    if task.data["status"] in ("completed", "cancelled"):
        raise api_error(ErrorCode.VMD_TASK_STATUS_INVALID, message="已完成或已取消的任务无法再次操作")

    await db.table("vmd_main_task").update({"status": "cancelled"}).eq("id", task_id).execute()
    return api_success(data={"status": "cancelled"}, message="任务已取消")


@router.get("/{task_id}/sub-tasks")
async def list_vmd_sub_tasks(req: Request, task_id: str, user_id: str = Depends(get_current_user_id)):
    """获取任务下的子任务审计日志"""
    db = getattr(req.state, "db", None)
    if not db:
        return api_success(data={"sub_tasks": []})

    result = (
        await db.table("vmd_sub_task_audit")
        .select("*")
        .eq("main_task_id", task_id)
        .order("executed_at", desc=True)
        .execute()
    )
    return api_success(data={"sub_tasks": result.data or []})
