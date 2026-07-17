"""VMD 任务路由。"""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, field_validator

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.scientific_instrument_domain import (
    build_instrument_context,
    normalize_instrument_line,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vmd/tasks", tags=["VMD Tasks"])


class CreateVMDTaskRequest(BaseModel):
    title: str = Field(min_length=2, max_length=500)
    description: str = Field(default="", max_length=5000)
    scene_code: str = Field(min_length=1, max_length=100)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    deadline: datetime | None = None
    instrument_line_code: str | None = None
    application_field: str | None = Field(default=None, max_length=200)
    target_product_models: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("instrument_line_code")
    @classmethod
    def validate_instrument_line(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_instrument_line(value)
        if not normalized:
            raise ValueError("不支持的科学仪器产品线")
        return normalized

    @field_validator("target_product_models")
    @classmethod
    def clean_product_models(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()][:20]


def _get_admin_db():
    """获取 admin client (绕过 RLS, 因为 vmd_main_task 的 RLS 依赖 app.current_org_id session 变量)"""
    from app.core.database import supabase

    if not supabase:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")
    return supabase


@router.get("")
async def list_vmd_tasks(
    req: Request,
    status: str | None = Query(None),
    priority: str | None = Query(None),
    instrument_line_code: str | None = Query(None),
    user_id: str = Depends(get_current_user_id),
):
    """获取 VMD 任务列表，支持状态和优先级过滤"""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        return api_success(data={"tasks": []})

    db = _get_admin_db()
    query = (
        db.table("vmd_main_task")
        .select("*")
        .eq("tenant_id", str(org_id))
        .order("create_time", desc=True)
    )

    if status:
        query = query.eq("status", status)
    if priority:
        query = query.eq("priority", priority)
    if isinstance(instrument_line_code, str) and instrument_line_code:
        normalized_line = normalize_instrument_line(instrument_line_code)
        if normalized_line:
            query = query.eq("instrument_line_code", normalized_line)

    result = await query.execute()
    return api_success(data={"tasks": result.data or []})


@router.post("")
async def create_vmd_task(
    body: CreateVMDTaskRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建带科学仪器领域上下文的 VMD 作战任务。"""

    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, message="未识别当前企业")

    now = datetime.now(UTC)
    task_code = f"VMD-{now:%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
    domain_context = build_instrument_context(
        body.instrument_line_code,
        application_field=body.application_field,
        product_models=body.target_product_models,
    )
    payload = {
        "tenant_id": str(org_id),
        "organization_id": str(org_id),
        "task_code": task_code,
        "user_id": user_id,
        "created_by": user_id,
        "title": body.title.strip(),
        "description": body.description.strip(),
        "original_input": body.description.strip() or body.title.strip(),
        "scene_code": body.scene_code,
        "status": "pending",
        "priority": body.priority,
        "deadline": body.deadline.isoformat() if body.deadline else None,
        "instrument_line_code": body.instrument_line_code,
        "application_field": body.application_field,
        "target_product_models": body.target_product_models,
        "domain_context": domain_context,
    }
    result = await _get_admin_db().table("vmd_main_task").insert(payload).execute()
    record = (result.data or [payload])[0]
    return api_success(data=record, message="作战任务已创建")


@router.get("/{task_id}")
async def get_vmd_task_detail(
    req: Request, task_id: str, user_id: str = Depends(get_current_user_id)
):
    """获取单个 VMD 任务详情"""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, message="数据库连接未配置")

    db = _get_admin_db()

    # 支持 task_code 或 UUID
    column = "id" if task_id.isdigit() else "task_code"
    result = (
        await db.table("vmd_main_task")
        .select("*")
        .eq(column, task_id)
        .eq("tenant_id", str(org_id))
        .maybe_single()
        .execute()
    )

    if not result.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, message="任务不存在")

    return api_success(data=result.data)


@router.post("/{task_id}/pause")
async def pause_vmd_task(
    req: Request, task_id: str, user_id: str = Depends(get_current_user_id)
):
    """暂停 VMD 任务"""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR)

    db = _get_admin_db()

    # 1. 检查任务是否存在及当前状态
    task = (
        await db.table("vmd_main_task")
        .select("status")
        .eq("id", task_id)
        .eq("tenant_id", str(org_id))
        .maybe_single()
        .execute()
    )
    if not task.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, message="任务不存在")

    if task.data["status"] != "running":
        raise api_error(
            ErrorCode.VMD_TASK_STATUS_INVALID, message="只有进行中的任务可以暂停"
        )

    # 2. 更新状态
    await db.table("vmd_main_task").update({"status": "paused"}).eq("id", task_id).eq(
        "tenant_id", str(org_id)
    ).execute()
    return api_success(data={"status": "paused"}, message="任务已暂停")


@router.post("/{task_id}/resume")
async def resume_vmd_task(
    req: Request, task_id: str, user_id: str = Depends(get_current_user_id)
):
    """恢复 VMD 任务"""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR)

    db = _get_admin_db()

    task = (
        await db.table("vmd_main_task")
        .select("status")
        .eq("id", task_id)
        .eq("tenant_id", str(org_id))
        .maybe_single()
        .execute()
    )
    if not task.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, message="任务不存在")

    if task.data["status"] != "paused":
        raise api_error(
            ErrorCode.VMD_TASK_STATUS_INVALID, message="只有已暂停的任务可以恢复"
        )

    await db.table("vmd_main_task").update({"status": "running"}).eq("id", task_id).eq(
        "tenant_id", str(org_id)
    ).execute()
    return api_success(data={"status": "running"}, message="任务已恢复")


@router.post("/{task_id}/cancel")
async def cancel_vmd_task(
    req: Request, task_id: str, user_id: str = Depends(get_current_user_id)
):
    """取消 VMD 任务"""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR)

    db = _get_admin_db()

    task = (
        await db.table("vmd_main_task")
        .select("status")
        .eq("id", task_id)
        .eq("tenant_id", str(org_id))
        .maybe_single()
        .execute()
    )
    if not task.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, message="任务不存在")

    if task.data["status"] in ("completed", "cancelled"):
        raise api_error(
            ErrorCode.VMD_TASK_STATUS_INVALID,
            message="已完成或已取消的任务无法再次操作",
        )

    await db.table("vmd_main_task").update({"status": "cancelled"}).eq(
        "id", task_id
    ).eq("tenant_id", str(org_id)).execute()
    return api_success(data={"status": "cancelled"}, message="任务已取消")


@router.get("/{task_id}/sub-tasks")
async def list_vmd_sub_tasks(
    req: Request, task_id: str, user_id: str = Depends(get_current_user_id)
):
    """获取任务下的子任务审计日志"""
    db = _get_admin_db()

    result = (
        await db.table("vmd_sub_task_audit")
        .select("*")
        .eq("main_task_id", task_id)
        .order("executed_at", desc=True)
        .execute()
    )
    return api_success(data={"sub_tasks": result.data or []})
