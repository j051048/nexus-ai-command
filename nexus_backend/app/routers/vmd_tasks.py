"""VMD Task Management API - Multi-agent task orchestration endpoints."""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_list, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vmd", tags=["VMD Tasks"])


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------


class CreateTaskRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500, description="任务标题")
    description: str = Field(..., min_length=1, description="任务描述（自然语言输入）")
    scene_code: str = Field(..., min_length=1, max_length=100, description="场景编码")
    priority: str = Field("medium", description="优先级: low/medium/high/urgent")
    deadline: str | None = Field(None, description="截止时间 (ISO格式)")


class AuditSubTaskRequest(BaseModel):
    action: str = Field(..., description="审核操作: approve/reject")
    comment: str | None = Field(None, max_length=2000, description="审核意见")


class UpdateAgentConfigRequest(BaseModel):
    system_prompt: str | None = Field(None, description="系统提示词")
    tool_whitelist: list[str] | None = Field(None, description="工具白名单")
    scene_codes: list[str] | None = Field(None, description="适用场景编码列表")
    max_retries: int | None = Field(None, ge=0, le=10, description="最大重试次数")
    timeout_ms: int | None = Field(None, ge=1000, le=600000, description="超时时间(ms)")
    model_code: str | None = Field(None, max_length=100, description="指定模型编码")
    status: str | None = Field(None, description="状态: active/inactive")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _generate_task_code() -> str:
    """Generate a unique task code: VMD-YYYYMMDD-XXXX"""
    date_part = datetime.utcnow().strftime("%Y%m%d")
    short_id = uuid.uuid4().hex[:6].upper()
    return f"VMD-{date_part}-{short_id}"


# ---------------------------------------------------------------------------
# Task CRUD endpoints
# ---------------------------------------------------------------------------


@router.post("/tasks")
async def create_task(
    body: CreateTaskRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建VMD任务"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        record = {
            "tenant_id": org_id,
            "task_code": _generate_task_code(),
            "title": body.title,
            "description": body.description,
            "scene_code": body.scene_code,
            "priority": body.priority,
            "deadline": body.deadline,
            "status": "pending",
            "user_id": user_id,
        }

        res = await client.table("vmd_main_task").insert(record).execute()
        task = res.data[0] if res.data else record
        return api_success(data={"task": task}, message="任务创建成功")
    except Exception as e:
        logger.error(f"Create task error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/tasks")
async def list_tasks(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    status: str | None = Query(None, description="状态筛选"),
    priority: str | None = Query(None, description="优先级筛选"),
    scene_code: str | None = Query(None, description="场景编码筛选"),
):
    """获取任务列表"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        # Count query
        count_query = client.table("vmd_main_task").select("id", count="exact").eq("tenant_id", org_id)
        if status:
            count_query = count_query.eq("status", status)
        if priority:
            count_query = count_query.eq("priority", priority)
        if scene_code:
            count_query = count_query.eq("scene_code", scene_code)

        count_res = await count_query.execute()
        total = count_res.count if count_res.count is not None else len(count_res.data or [])

        # Data query
        offset = (page - 1) * page_size
        data_query = (
            client.table("vmd_main_task")
            .select("*")
            .eq("tenant_id", org_id)
            .order("create_time", desc=True)
            .range(offset, offset + page_size - 1)
        )
        if status:
            data_query = data_query.eq("status", status)
        if priority:
            data_query = data_query.eq("priority", priority)
        if scene_code:
            data_query = data_query.eq("scene_code", scene_code)

        res = await data_query.execute()
        return api_list(items=res.data or [], total=total, page=page, page_size=page_size)
    except Exception as e:
        logger.error(f"List tasks error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取任务详情（含子任务、WBS结构、进度信息）"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        # Get main task
        task_res = await client.table("vmd_main_task").select("*").eq("id", task_id).maybe_single().execute()
        if not task_res.data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "任务不存在")

        task = task_res.data

        # Get sub-tasks
        sub_tasks_res = (
            await client.table("vmd_sub_task")
            .select("*")
            .eq("main_task_id", task_id)
            .order("sort_order", desc=False)
            .execute()
        )
        sub_tasks = sub_tasks_res.data or []

        # Calculate progress
        total_sub = len(sub_tasks)
        completed_sub = sum(1 for s in sub_tasks if s.get("status") == "completed")
        progress = round((completed_sub / total_sub * 100), 1) if total_sub > 0 else 0.0

        return api_success(
            data={
                "task": task,
                "sub_tasks": sub_tasks,
                "wbs_structure": task.get("wbs_structure"),
                "progress": {
                    "total_sub_tasks": total_sub,
                    "completed": completed_sub,
                    "percentage": progress,
                },
            }
        )
    except Exception as e:
        logger.error(f"Get task error: id={task_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/tasks/{task_id}/logs")
async def get_task_logs(
    task_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """获取任务执行日志"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        # Count
        count_res = await client.table("llm_call_log").select("id", count="exact").eq("main_task_id", task_id).execute()
        total = count_res.count if count_res.count is not None else len(count_res.data or [])

        # Data
        offset = (page - 1) * page_size
        res = (
            await client.table("llm_call_log")
            .select("*")
            .eq("main_task_id", task_id)
            .order("create_time", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )

        return api_list(items=res.data or [], total=total, page=page, page_size=page_size)
    except Exception as e:
        logger.error(f"Get task logs error: task={task_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---------------------------------------------------------------------------
# Task lifecycle endpoints
# ---------------------------------------------------------------------------


@router.post("/tasks/{task_id}/pause")
async def pause_task(
    task_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """暂停任务"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        # Verify task exists and is in executable state
        task_res = await client.table("vmd_main_task").select("id, status").eq("id", task_id).maybe_single().execute()
        if not task_res.data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "任务不存在")

        current_status = task_res.data.get("status")
        if current_status not in ("pending", "executing"):
            return api_error(ErrorCode.VALIDATION_INVALID_INPUT, f"当前状态({current_status})不允许暂停")

        await (
            client.table("vmd_main_task")
            .update({"status": "paused", "updated_by": user_id})
            .eq("id", task_id)
            .execute()
        )
        return api_success(data={"task_id": task_id, "status": "paused"}, message="任务已暂停")
    except Exception as e:
        logger.error(f"Pause task error: id={task_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/tasks/{task_id}/resume")
async def resume_task(
    task_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """恢复任务"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        task_res = await client.table("vmd_main_task").select("id, status").eq("id", task_id).maybe_single().execute()
        if not task_res.data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "任务不存在")

        if task_res.data.get("status") != "paused":
            return api_error(ErrorCode.VALIDATION_INVALID_INPUT, "只有暂停状态的任务可以恢复")

        await (
            client.table("vmd_main_task")
            .update({"status": "executing", "updated_by": user_id})
            .eq("id", task_id)
            .execute()
        )
        return api_success(data={"task_id": task_id, "status": "executing"}, message="任务已恢复执行")
    except Exception as e:
        logger.error(f"Resume task error: id={task_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """取消任务"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        task_res = await client.table("vmd_main_task").select("id, status").eq("id", task_id).maybe_single().execute()
        if not task_res.data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "任务不存在")

        current_status = task_res.data.get("status")
        if current_status in ("completed", "cancelled"):
            return api_error(ErrorCode.VALIDATION_INVALID_INPUT, f"当前状态({current_status})不允许取消")

        await (
            client.table("vmd_main_task")
            .update({"status": "cancelled", "updated_by": user_id})
            .eq("id", task_id)
            .execute()
        )
        return api_success(data={"task_id": task_id, "status": "cancelled"}, message="任务已取消")
    except Exception as e:
        logger.error(f"Cancel task error: id={task_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/tasks/{task_id}/retry")
async def retry_task(
    task_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """重试失败的子任务"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        # Verify task exists
        task_res = await client.table("vmd_main_task").select("id, status").eq("id", task_id).maybe_single().execute()
        if not task_res.data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "任务不存在")

        # Find failed sub-tasks
        failed_res = (
            await client.table("vmd_sub_task").select("id").eq("main_task_id", task_id).eq("status", "failed").execute()
        )
        failed_sub_tasks = failed_res.data or []

        if not failed_sub_tasks:
            return api_success(data={"retried_count": 0}, message="没有需要重试的失败子任务")

        # Reset failed sub-tasks to pending
        failed_ids = [s["id"] for s in failed_sub_tasks]
        for sub_id in failed_ids:
            await (
                client.table("vmd_sub_task")
                .update({"status": "pending", "retry_count": 0, "error_message": None, "updated_by": user_id})
                .eq("id", sub_id)
                .execute()
            )

        # Set main task back to executing
        await (
            client.table("vmd_main_task")
            .update({"status": "executing", "updated_by": user_id})
            .eq("id", task_id)
            .execute()
        )

        return api_success(
            data={"task_id": task_id, "retried_count": len(failed_ids), "status": "executing"},
            message=f"已重新提交 {len(failed_ids)} 个失败子任务",
        )
    except Exception as e:
        logger.error(f"Retry task error: id={task_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---------------------------------------------------------------------------
# Sub-task audit endpoint
# ---------------------------------------------------------------------------


@router.post("/sub-tasks/{sub_task_id}/audit")
async def audit_sub_task(
    sub_task_id: str,
    body: AuditSubTaskRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """审核子任务"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        if body.action not in ("approve", "reject"):
            return api_error(ErrorCode.VALIDATION_INVALID_INPUT, "action 必须为 approve 或 reject")

        # Verify sub-task exists
        sub_res = (
            await client.table("vmd_sub_task")
            .select("id, status, main_task_id")
            .eq("id", sub_task_id)
            .maybe_single()
            .execute()
        )
        if not sub_res.data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "子任务不存在")

        if body.action == "approve":
            update_data = {
                "review_status": "approved",
                "review_comment": body.comment,
                "reviewed_by": user_id,
                "reviewed_at": datetime.utcnow().isoformat(),
            }
        else:
            update_data = {
                "review_status": "rejected",
                "review_comment": body.comment,
                "reviewed_by": user_id,
                "reviewed_at": datetime.utcnow().isoformat(),
                "status": "pending",  # Allow re-execution
            }

        await client.table("vmd_sub_task").update(update_data).eq("id", sub_task_id).execute()

        return api_success(
            data={"sub_task_id": sub_task_id, "review_status": update_data["review_status"]},
            message=f"子任务已{'通过' if body.action == 'approve' else '驳回'}",
        )
    except Exception as e:
        logger.error(f"Audit sub-task error: id={sub_task_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---------------------------------------------------------------------------
# Agent config endpoints
# ---------------------------------------------------------------------------


@router.get("/agents/config")
async def list_agent_configs(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取所有Agent角色配置"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        res = await client.table("vmd_agent_config").select("*").eq("tenant_id", org_id).order("agent_code").execute()
        return api_success(data={"agents": res.data or []})
    except Exception as e:
        logger.error(f"List agent configs error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/agents/config/{agent_code}")
async def update_agent_config(
    agent_code: str,
    body: UpdateAgentConfigRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新Agent配置"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        update_data = body.model_dump(exclude_none=True)
        if not update_data:
            return api_error(ErrorCode.VALIDATION_INVALID_INPUT, "无更新内容")

        update_data["updated_by"] = user_id

        res = (
            await client.table("vmd_agent_config")
            .update(update_data)
            .eq("agent_code", agent_code)
            .eq("tenant_id", org_id)
            .execute()
        )
        if not res.data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "Agent配置不存在")

        return api_success(data={"agent": res.data[0]}, message="Agent配置已更新")
    except Exception as e:
        logger.error(f"Update agent config error: code={agent_code} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
