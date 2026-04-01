"""销售目标和指标 API 路由"""

import logging
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sales", tags=["Sales"])


@router.get("/targets")
async def list_targets(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取销售目标"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)

        result = await db.table("sales_targets").select("*").eq("tenant_id", org_id).execute()
        return api_success(data={"targets": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list targets: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取目标失败")


@router.get("/metrics")
async def list_metrics(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取销售指标"""
    try:
        org_id = getattr(req.state, "org_id", None)
        db = getattr(req.state, "db", None)

        query = db.table("sales_metrics").select("*")
        if org_id:
            query = query.eq("tenant_id", org_id)

        result = await query.execute()
        return api_success(data={"metrics": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list metrics: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取指标失败")
