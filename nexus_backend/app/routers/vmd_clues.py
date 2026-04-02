"""VMD 线索路由"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Request, Query
from app.core.auth import get_current_user_id
from app.core.errors import api_success, api_error

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vmd/clues", tags=["VMD Clues"])


@router.get("")
async def list_vmd_clues(
    req: Request,
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user_id)
):
    """获取商机线索列表"""
    try:
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
    except Exception as e:
        logger.error(f"Failed to list VMD clues: {e}")
        return api_error(message="获取线索列表失败")


@router.get("/{clue_id}")
async def get_vmd_clue_detail(
    req: Request,
    clue_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """获取单个线索详情"""
    try:
        db = getattr(req.state, "db", None)
        if not db:
            return api_error(message="数据库连接未配置")

        # 支持 clue_code 或 ID
        column = "clue_code" if not clue_id.isdigit() and len(clue_id) < 15 else "id"
        result = await db.table("business_clue").select("*").eq(column, clue_id).single().execute()
        
        if not result.data:
            return api_error(message="线索不存在", code=404)
            
        return api_success(data=result.data)
    except Exception as e:
        logger.error(f"Failed to get VMD clue detail: {e}")
        return api_error(message="获取线索详情失败")
