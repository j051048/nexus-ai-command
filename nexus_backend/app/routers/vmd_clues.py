"""VMD 线索路由"""

import logging

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vmd/clues", tags=["VMD Clues"])


@router.get("")
async def list_vmd_clues(
    req: Request,
    status: str | None = Query(None),
    priority: str | None = Query(None),
    user_id: str = Depends(get_current_user_id),
):
    """获取商机线索列表"""
    db = getattr(req.state, "db", None)
    if not db:
        return api_success(data={"clues": []})

    query = db.table("business_clue").select("*").order("create_time", desc=True)

    if status:
        query = query.eq("status", status)
    if priority:
        query = query.eq("priority", priority)

    result = await query.execute()
    return api_success(data={"clues": result.data or []})


@router.get("/{clue_id}")
async def get_vmd_clue_detail(req: Request, clue_id: str, user_id: str = Depends(get_current_user_id)):
    """获取单个线索详情"""
    db = getattr(req.state, "db", None)
    if not db:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, message="数据库连接未配置")

    # 支持 clue_code 或 ID
    column = "clue_code" if not clue_id.isdigit() and len(clue_id) < 15 else "id"
    result = await db.table("business_clue").select("*").eq(column, clue_id).maybe_single().execute()

    if not result.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, message="线索不存在")

    return api_success(data=result.data)
