"""
数据备份路由

提供数据备份创建、列表、恢复预览、恢复和自动备份调度等端点。
"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.dependencies import require_role
from app.core.errors import ErrorCode, api_error, api_success
from app.services.backup_service import backup_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backups", tags=["Backups"])

# 备份操作需要管理员权限
require_backup_admin = require_role(["admin", "founder", "boss"])


# ============== Request Models ==============


class CreateBackupRequest(BaseModel):
    tables: list[str] | None = None


class RestoreRequest(BaseModel):
    tables: list[str] | None = None


class ScheduleRequest(BaseModel):
    frequency: str = "daily"
    tables: list[str] | None = None


# ============== Endpoints ==============


@router.post("/create")
async def create_backup(
    request: Request,
    body: CreateBackupRequest,
    user_id: str = Depends(require_backup_admin),
):
    """创建组织数据备份"""
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "需要组织上下文")

    client = getattr(request.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    try:
        result = await backup_service.create_backup(
            org_id=org_id,
            tables=body.tables,
            created_by=user_id,
            db=client,
        )
        return api_success(data=result, message="备份创建成功")
    except Exception as e:
        logger.error(f"创建备份失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("")
async def list_backups(
    request: Request,
    user_id: str = Depends(require_backup_admin),
):
    """列出组织的备份记录"""
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "需要组织上下文")

    client = getattr(request.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    try:
        backups = await backup_service.list_backups(org_id=org_id, db=client)
        return api_success(data=backups)
    except Exception as e:
        logger.error(f"列出备份失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/{backup_id}/preview")
async def restore_preview(
    backup_id: str,
    request: Request,
    user_id: str = Depends(require_backup_admin),
):
    """恢复预览: 显示将恢复的数据统计"""
    client = getattr(request.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    try:
        preview = await backup_service.restore_preview(backup_id=backup_id, db=client)
        if preview.get("error"):
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, preview["error"])
        return api_success(data=preview)
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"恢复预览失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/{backup_id}/restore")
async def restore_backup(
    backup_id: str,
    request: Request,
    body: RestoreRequest,
    user_id: str = Depends(require_backup_admin),
):
    """恢复数据（需要确认）"""
    client = getattr(request.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    try:
        result = await backup_service.restore_backup(
            backup_id=backup_id,
            tables=body.tables,
            db=client,
        )
        if result.get("error"):
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, result["error"])
        return api_success(data=result, message="数据恢复完成")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"恢复数据失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/schedule")
async def set_backup_schedule(
    request: Request,
    body: ScheduleRequest,
    user_id: str = Depends(require_backup_admin),
):
    """设置自动备份计划"""
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "需要组织上下文")

    client = getattr(request.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    try:
        result = await backup_service.schedule_auto_backup(
            org_id=org_id,
            frequency=body.frequency,
            tables=body.tables,
            db=client,
        )
        return api_success(data=result, message="备份计划已设置")
    except Exception as e:
        logger.error(f"设置备份计划失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
