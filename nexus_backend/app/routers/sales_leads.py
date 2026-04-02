"""销售线索管理 API 路由"""

import logging
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sales-leads", tags=["Sales Leads"])


class LeadCreate(BaseModel):
    customer_name: str
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    stage: str = "initial"
    source: str | None = None
    notes: str | None = None


class LeadUpdate(BaseModel):
    customer_name: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    stage: str | None = None
    source: str | None = None
    notes: str | None = None


@router.get("")
async def list_leads(
    req: Request,
    stage: str | None = None,
    skip: int = 0,
    limit: int = 50,
    user_id: str = Depends(get_current_user_id),
):
    """获取销售线索列表"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        query = db.table("sales_leads").select("*").eq("organization_id", org_id)
        if stage:
            query = query.eq("stage", stage)

        result = await query.range(skip, skip + limit - 1).execute()
        return api_success(data={"leads": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list leads: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取线索失败")


@router.post("")
async def create_lead(
    body: LeadCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建销售线索"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        data = body.model_dump()
        data["organization_id"] = org_id
        data["user_id"] = user_id

        result = await db.table("sales_leads").insert(data).execute()
        return api_success(data={"lead": result.data[0] if result.data else None}, message="线索创建成功")
    except Exception as e:
        logger.error(f"Failed to create lead: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "创建线索失败")


@router.put("/{lead_id}")
async def update_lead(
    lead_id: str,
    body: LeadUpdate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新销售线索"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")
        data = body.model_dump(exclude_none=True)

        result = await db.table("sales_leads").update(data).eq("id", lead_id).eq("organization_id", org_id).execute()
        return api_success(data={"lead": result.data[0] if result.data else None}, message="线索已更新")
    except Exception as e:
        logger.error(f"Failed to update lead: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "更新线索失败")
