"""
超级管理员路由 - 平台级管理端点

所有端点需要 super_admin 角色验证。
使用全局 supabase client（service key），不使用 request.state.db（RLS-scoped），
因为超级管理员需要跨组织访问数据。
"""

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.dependencies import require_role
from app.core.errors import ErrorCode, api_error, api_list, api_success
from app.services.super_admin_service import super_admin_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["SuperAdmin"])

# super_admin 角色依赖
require_super_admin = require_role(["super_admin", "founder"])


# ============== Request Models ==============


class SuspendRequest(BaseModel):
    reason: str


# ============== Endpoints ==============


@router.get("/organizations")
async def list_organizations(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None),
    user_id: str = Depends(require_super_admin),
):
    """列出所有组织（支持搜索和状态筛选）"""
    try:
        result = await super_admin_service.list_organizations(
            page=page, limit=limit, search=search, status=status
        )
        return api_list(
            items=result["organizations"],
            total=result["total"],
            page=result["page"],
            page_size=result["limit"],
        )
    except Exception as e:
        logger.error(f"列出组织失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "超级管理员操作失败")


@router.get("/organizations/{org_id}")
async def get_organization_detail(
    org_id: str,
    user_id: str = Depends(require_super_admin),
):
    """获取组织详情（含用户数、订阅状态、用量）"""
    try:
        result = await super_admin_service.get_organization_detail(org_id)
        if not result:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "组织不存在")
        return api_success(data=result)
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"获取组织详情失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "超级管理员操作失败")


@router.post("/organizations/{org_id}/suspend")
async def suspend_organization(
    org_id: str,
    body: SuspendRequest,
    user_id: str = Depends(require_super_admin),
):
    """暂停组织"""
    try:
        success = await super_admin_service.suspend_organization(org_id, body.reason)
        if success:
            return api_success(
                data={"org_id": org_id, "status": "suspended"}, message="组织已暂停"
            )
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "组织不存在或操作失败")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"暂停组织失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "超级管理员操作失败")


@router.post("/organizations/{org_id}/unsuspend")
async def unsuspend_organization(
    org_id: str,
    user_id: str = Depends(require_super_admin),
):
    """恢复组织"""
    try:
        success = await super_admin_service.unsuspend_organization(org_id)
        if success:
            return api_success(
                data={"org_id": org_id, "status": "active"}, message="组织已恢复"
            )
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "组织不存在或操作失败")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"恢复组织失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "超级管理员操作失败")


@router.get("/stats")
async def get_platform_stats(
    user_id: str = Depends(require_super_admin),
):
    """获取平台级统计数据"""
    try:
        stats = await super_admin_service.get_platform_stats()
        return api_success(data=stats)
    except Exception as e:
        logger.error(f"获取平台统计失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "超级管理员操作失败")


@router.get("/system-health")
async def get_system_health(
    user_id: str = Depends(require_super_admin),
):
    """系统健康检查"""
    try:
        health = await super_admin_service.get_system_health()
        return api_success(data=health)
    except Exception as e:
        logger.error(f"系统健康检查失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "超级管理员操作失败")


@router.get("/audit-logs")
async def list_audit_logs(
    action: str | None = Query(default=None),
    user_id_filter: str | None = Query(default=None, alias="filter_user_id"),
    org_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(require_super_admin),
):
    """全局审计日志查看"""
    try:
        filters = {}
        if action:
            filters["action"] = action
        if user_id_filter:
            filters["user_id"] = user_id_filter
        if org_id:
            filters["org_id"] = org_id
        if date_from:
            filters["date_from"] = date_from
        if date_to:
            filters["date_to"] = date_to

        logs = await super_admin_service.list_audit_logs_global(
            filters=filters, limit=limit, offset=offset
        )
        return api_success(data=logs)
    except Exception as e:
        logger.error(f"获取审计日志失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "超级管理员操作失败")
