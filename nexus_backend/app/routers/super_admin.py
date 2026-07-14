"""
超级管理员路由 - 平台级管理端点

所有端点需要 super_admin 角色验证。
使用全局 supabase client（service key），不使用 request.state.db（RLS-scoped），
因为超级管理员需要跨组织访问数据。
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.dependencies import require_platform_super_admin
from app.core.errors import ErrorCode, api_error, api_list, api_success
from app.services.super_admin_service import super_admin_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["SuperAdmin"])

# super_admin 角色依赖
# Platform super-admin endpoints intentionally bypass tenant-scoped RLS through
# the service-role client in SuperAdminService. Keep this dependency strictly
# limited to the dedicated platform role; tenant founders/bosses must use
# tenant-scoped organization endpoints instead.
require_super_admin = require_platform_super_admin()


# ============== Request Models ==============


class SuspendRequest(BaseModel):
    reason: str


class ChangePlanRequest(BaseModel):
    plan: str
    reason: str = ""


class UpdateQuotasRequest(BaseModel):
    monthly_token_limit: int | None = None
    monthly_api_call_limit: int | None = None
    storage_limit_mb: int | None = None
    reason: str = ""


class ManageTrialRequest(BaseModel):
    action: str = "start"
    days: int = 14
    plan: str = "professional"
    reason: str = ""


class SetAccessRequest(BaseModel):
    plan: str
    expires_at: datetime | None = None
    reason: str = Field(min_length=2, max_length=1000)


class SubscriptionDecisionRequest(BaseModel):
    decision: str
    reason: str = Field(min_length=2, max_length=1000)
    plan: str | None = None
    expires_at: datetime | None = None


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
        success = await super_admin_service.suspend_organization(
            org_id, body.reason, admin_user_id=user_id
        )
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
        success = await super_admin_service.unsuspend_organization(
            org_id, admin_user_id=user_id
        )
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


@router.post("/organizations/{org_id}/change-plan")
async def admin_change_plan(
    org_id: str,
    body: ChangePlanRequest,
    user_id: str = Depends(require_super_admin),
):
    """超级管理员手动变更组织订阅计划"""
    try:
        result = await super_admin_service.admin_change_plan(
            org_id=org_id, plan=body.plan, reason=body.reason, admin_user_id=user_id
        )
        return api_success(data=result, message="订阅计划已变更")
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"变更订阅计划失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "超级管理员操作失败")


@router.post("/organizations/{org_id}/update-quotas")
async def admin_update_quotas(
    org_id: str,
    body: UpdateQuotasRequest,
    user_id: str = Depends(require_super_admin),
):
    """超级管理员手动调整组织配额"""
    try:
        quotas = {
            k: v
            for k, v in body.model_dump(exclude={"reason"}).items()
            if v is not None
        }
        result = await super_admin_service.admin_update_quotas(
            org_id=org_id, quotas=quotas, reason=body.reason, admin_user_id=user_id
        )
        return api_success(data=result, message="配额已更新")
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"更新配额失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "超级管理员操作失败")


@router.put("/organizations/{org_id}/access")
async def admin_set_access(
    org_id: str,
    body: SetAccessRequest,
    user_id: str = Depends(require_super_admin),
):
    """Grant, renew, or revoke an organization's membership access."""
    try:
        result = await super_admin_service.admin_set_access(
            org_id=org_id,
            plan=body.plan,
            expires_at=body.expires_at.isoformat() if body.expires_at else None,
            reason=body.reason,
            admin_user_id=user_id,
        )
        return api_success(data=result, message="会员权益已更新")
    except ValueError as exc:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(exc))
    except Exception as exc:
        logger.error("Failed to update organization access: %s", exc)
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "会员权益更新失败")


@router.get("/subscription-requests")
async def list_subscription_requests(
    status: str = Query(default="pending"),
    limit: int = Query(default=100, ge=1, le=500),
    user_id: str = Depends(require_super_admin),
):
    """List membership activation and renewal requests."""
    try:
        requests = await super_admin_service.list_subscription_requests(
            status=status, limit=limit
        )
        return api_success(data={"requests": requests})
    except Exception as exc:
        logger.error("Failed to list subscription requests: %s", exc)
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "会员申请加载失败")


@router.post("/subscription-requests/{request_id}/decision")
async def decide_subscription_request(
    request_id: str,
    body: SubscriptionDecisionRequest,
    user_id: str = Depends(require_super_admin),
):
    """Approve or reject one membership request."""
    try:
        result = await super_admin_service.decide_subscription_request(
            request_id=request_id,
            decision=body.decision,
            reason=body.reason,
            admin_user_id=user_id,
            plan=body.plan,
            expires_at=body.expires_at.isoformat() if body.expires_at else None,
        )
        return api_success(data=result, message="会员申请已处理")
    except ValueError as exc:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(exc))
    except Exception as exc:
        logger.error("Failed to decide subscription request: %s", exc)
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "会员申请处理失败")


@router.post("/organizations/{org_id}/manage-trial")
async def admin_manage_trial(
    org_id: str,
    body: ManageTrialRequest,
    user_id: str = Depends(require_super_admin),
):
    """超级管理员手动管理组织试用期"""
    try:
        result = await super_admin_service.admin_manage_trial(
            org_id=org_id,
            action=body.action,
            days=body.days,
            plan=body.plan,
            reason=body.reason,
            admin_user_id=user_id,
        )
        return api_success(data=result, message="试用期已更新")
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"管理试用期失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "超级管理员操作失败")
