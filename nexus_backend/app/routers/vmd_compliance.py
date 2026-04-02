"""VMD 合规路由"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Request, Query
from app.core.auth import get_current_user_id
from app.core.errors import api_success, api_error

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vmd/compliance", tags=["VMD Compliance"])


@router.get("/history")
async def list_vmd_compliance_history(
    req: Request,
    user_id: str = Depends(get_current_user_id)
):
    """获取合规审计历史列表"""
    try:
        db = getattr(req.state, "db", None)
        if not db:
            return api_success(data={"history": []})

        # 目前使用 vmd_reports 存储历史
        result = await db.table("vmd_reports").select("*").order("created_at", desc=True).execute()
        return api_success(data=result.data or [])
    except Exception as e:
        logger.error(f"Failed to list compliance history: {e}")
        return api_error(message="获取审计历史失败")


@router.get("/rules")
async def list_vmd_compliance_rules(
    req: Request,
    user_id: str = Depends(get_current_user_id)
):
    """获取合规检查规则"""
    try:
        # 暂时返回空或默认规则，避免 404
        return api_success(data=[])
    except Exception as e:
        logger.error(f"Failed to list compliance rules: {e}")
        return api_error(message="获取规则失败")
