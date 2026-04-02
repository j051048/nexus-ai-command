"""VMD 任务路由"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Request, Query
from app.core.auth import get_current_user_id
from app.core.errors import api_success, api_error

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vmd/tasks", tags=["VMD Tasks"])


@router.get("")
async def list_vmd_tasks(
    req: Request,
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user_id)
):
    """获取 VMD 任务列表，支持状态和优先级过滤"""
    try:
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
    except Exception as e:
        logger.error(f"Failed to list VMD tasks: {e}")
        return api_error(message="获取任务列表失败")


@router.get("/{task_id}")
async def get_vmd_task_detail(
    req: Request,
    task_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """获取单个 VMD 任务详情"""
    try:
        db = getattr(req.state, "db", None)
        if not db:
            return api_error(message="数据库连接未配置")

        # 支持 task_code 或 UUID
        column = "task_code" if not task_id.replace('-', '').isalnum() or len(task_id) < 20 else "id"
        result = await db.table("vmd_main_task").select("*").eq(column, task_id).single().execute()
        
        if not result.data:
            return api_error(message="任务不存在", code=404)
            
        return api_success(data=result.data)
    except Exception as e:
        logger.error(f"Failed to get VMD task detail: {e}")
        return api_error(message="获取任务详情失败")
