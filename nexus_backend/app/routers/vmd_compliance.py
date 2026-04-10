"""VMD 合规路由"""

import logging

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vmd/compliance", tags=["VMD Compliance"])


def _get_admin_db():
    """获取 admin client (绕过 RLS)"""
    from app.core.database import supabase

    if not supabase:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")
    return supabase


@router.get("/history")
async def list_vmd_compliance_history(
    req: Request, user_id: str = Depends(get_current_user_id)
):
    """获取合规审计历史列表"""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        return api_success(data=[])

    db = _get_admin_db()

    try:
        result = (
            await db.table("vmd_reports")
            .select("*")
            .eq("tenant_id", str(org_id))
            .order("created_at", desc=True)
            .execute()
        )
        return api_success(data=result.data or [])
    except Exception as e:
        logger.error(f"Failed to list compliance history: {e}")
        raise api_error(ErrorCode.DB_QUERY_ERROR, message="获取审计历史失败")


@router.get("/rules")
async def list_vmd_compliance_rules(
    req: Request, user_id: str = Depends(get_current_user_id)
):
    """获取合规检查规则"""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        return api_success(data=[])

    db = _get_admin_db()

    try:
        result = (
            await db.table("compliance_rule")
            .select("*")
            .eq("tenant_id", str(org_id))
            .execute()
        )
        return api_success(data=result.data or [])
    except Exception as e:
        logger.error(f"Failed to list compliance rules: {e}")
        raise api_error(ErrorCode.DB_QUERY_ERROR, message="获取合规规则失败")
