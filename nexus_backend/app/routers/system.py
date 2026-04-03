"""仪表板配置和审计日志 API 路由"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/system", tags=["System"])


class DashboardConfigUpdate(BaseModel):
    config: dict


@router.get("/dashboard-configs")
async def get_dashboard_config(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取仪表板配置"""
    try:
        db = getattr(req.state, "db", None)
        result = await db.table("dashboard_configs").select("*").eq("user_id", user_id).maybe_single().execute()
        return api_success(data={"config": result.data})
    except Exception as e:
        logger.error(f"Failed to get dashboard config: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取配置失败")


@router.post("/dashboard-configs")
async def upsert_dashboard_config(
    body: DashboardConfigUpdate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新仪表板配置"""
    try:
        db = getattr(req.state, "db", None)
        data = {"user_id": user_id, "config": body.config}
        result = await db.table("dashboard_configs").upsert(data).execute()
        return api_success(data={"config": result.data[0] if result.data else None}, message="配置已保存")
    except Exception as e:
        logger.error(f"Failed to upsert dashboard config: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "保存配置失败")


@router.get("/audit-logs")
async def list_audit_logs(
    req: Request,
    limit: int = 200,
    user_id: str = Depends(get_current_user_id),
):
    """获取审计日志"""
    try:
        org_id = getattr(req.state, "org_id", None)
        db = getattr(req.state, "db", None)

        query = db.table("audit_logs").select("*").order("created_at", desc=True).limit(min(limit, 200))
        if org_id:
            query = query.eq("organization_id", org_id)

        result = await query.execute()
        return api_success(data={"logs": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list audit logs: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取日志失败")
