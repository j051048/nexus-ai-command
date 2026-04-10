"""VMD 线索路由"""

import logging

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vmd/clues", tags=["VMD Clues"])


def _get_admin_db():
    """获取 admin client (绕过 RLS, 因为 business_clue 的 RLS 依赖 app.current_org_id)"""
    from app.core.database import supabase

    if not supabase:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")
    return supabase


@router.get("")
async def list_vmd_clues(
    req: Request,
    status: str | None = Query(None),
    priority: str | None = Query(None),
    user_id: str = Depends(get_current_user_id),
):
    """获取商机线索列表"""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        return api_success(data={"clues": []})

    db = _get_admin_db()
    query = (
        db.table("business_clue")
        .select("*")
        .eq("tenant_id", str(org_id))
        .order("create_time", desc=True)
    )

    if status:
        query = query.eq("status", status)
    if priority:
        query = query.eq("priority", priority)

    result = await query.execute()
    return api_success(data={"clues": result.data or []})


@router.get("/{clue_id}")
async def get_vmd_clue_detail(
    req: Request, clue_id: str, user_id: str = Depends(get_current_user_id)
):
    """获取单个线索详情"""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, message="数据库连接未配置")

    db = _get_admin_db()

    # 支持 clue_code 或 ID
    column = "clue_code" if not clue_id.isdigit() and len(clue_id) < 15 else "id"
    result = (
        await db.table("business_clue")
        .select("*")
        .eq(column, clue_id)
        .eq("tenant_id", str(org_id))
        .maybe_single()
        .execute()
    )

    if not result.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, message="线索不存在")

    return api_success(data=result.data)
