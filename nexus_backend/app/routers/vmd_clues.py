"""VMD Clues API - Business clue/lead management endpoints."""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_list, api_success
from app.services.clue_service import clue_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vmd", tags=["VMD Clues"])


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------


class CreateClueRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500, description="线索标题")
    content: str | None = Field(None, description="线索详细内容")
    source: str = Field("other", max_length=50, description="来源")
    industry: str | None = Field(None, max_length=100, description="行业")
    region: str | None = Field(None, max_length=100, description="地区")
    estimated_value: float | None = Field(None, ge=0, description="预估价值")
    priority: str = Field("medium", description="优先级: low/medium/high")
    tags: list[str] | None = Field(None, description="标签列表")


class UpdateClueRequest(BaseModel):
    title: str | None = Field(None, max_length=500)
    content: str | None = None
    source: str | None = Field(None, max_length=50)
    industry: str | None = Field(None, max_length=100)
    region: str | None = Field(None, max_length=100)
    estimated_value: float | None = Field(None, ge=0)
    priority: str | None = None
    status: str | None = None
    assigned_to: str | None = None
    tags: list[str] | None = None


class FollowUpRequest(BaseModel):
    action: str = Field(..., min_length=1, max_length=100, description="跟进动作")
    content: str = Field(..., min_length=1, description="跟进内容")
    next_action: str | None = Field(None, max_length=200, description="下一步动作")
    next_action_date: str | None = Field(None, description="下一步动作日期 (ISO格式)")


# ---------------------------------------------------------------------------
# Clue CRUD endpoints
# ---------------------------------------------------------------------------


@router.post("/clues")
async def create_clue(
    body: CreateClueRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建商机线索"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        clue_data = {
            "title": body.title,
            "description": body.content or "",
            "source": body.source,
            "industry": body.industry,
            "region": body.region,
            "estimated_value": body.estimated_value or 0,
            "priority": body.priority,
            "tags": body.tags,
            "created_by": user_id,
        }

        result = await clue_service.create_clue(
            tenant_id=org_id,
            data=clue_data,
            db=client,
        )
        return api_success(data={"clue": result}, message="线索创建成功")
    except ValueError as e:
        return api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
    except Exception as e:
        logger.error(f"Create clue error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/clues")
async def list_clues(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    status: str | None = Query(None, description="状态筛选"),
    source: str | None = Query(None, description="来源筛选"),
    priority: str | None = Query(None, description="优先级筛选"),
    assigned_to: str | None = Query(None, description="负责人筛选"),
    keyword: str | None = Query(None, description="标题关键词搜索"),
):
    """获取线索列表（分页、筛选）"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        filters = {}
        if status:
            filters["status"] = status
        if source:
            filters["source"] = source
        if priority:
            filters["level"] = priority
        if assigned_to:
            filters["assigned_to"] = assigned_to
        if keyword:
            filters["search"] = keyword

        result = await clue_service.list_clues(
            tenant_id=org_id,
            filters=filters,
            page=page,
            page_size=page_size,
            db=client,
        )

        return api_list(
            items=result.get("items", []),
            total=result.get("total", 0),
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        logger.error(f"List clues error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/clues/stats/overview")
async def get_clue_stats(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取线索统计概览（按状态、来源、优先级）"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        result = await clue_service.get_clue_stats(
            tenant_id=org_id,
            db=client,
        )

        return api_success(data={"stats": result})
    except Exception as e:
        logger.error(f"Get clue stats error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/clues/{clue_id}")
async def get_clue(
    clue_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取线索详情（含跟进历史）"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        clue = await clue_service.get_clue(
            tenant_id=org_id,
            clue_id=clue_id,
            db=client,
        )
        if not clue:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "线索不存在")

        # Fetch follow-up history
        try:
            follow_ups_res = (
                await client.table("clue_follow_up")
                .select("*")
                .eq("clue_id", clue_id)
                .order("created_at", desc=True)
                .execute()
            )
            follow_ups = follow_ups_res.data or []
        except Exception:
            follow_ups = []

        return api_success(data={"clue": clue, "follow_ups": follow_ups})
    except Exception as e:
        logger.error(f"Get clue error: id={clue_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/clues/{clue_id}")
async def update_clue(
    clue_id: str,
    body: UpdateClueRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新线索"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        update_data = body.model_dump(exclude_none=True)
        if not update_data:
            return api_error(ErrorCode.VALIDATION_INVALID_INPUT, "无更新内容")

        # Map content -> description for service layer
        if "content" in update_data:
            update_data["description"] = update_data.pop("content")

        update_data["updated_by"] = user_id

        result = await clue_service.update_clue(
            tenant_id=org_id,
            clue_id=clue_id,
            data=update_data,
            db=client,
        )
        if not result:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "线索不存在")

        return api_success(data={"clue": result}, message="线索已更新")
    except ValueError as e:
        return api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
    except Exception as e:
        logger.error(f"Update clue error: id={clue_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.delete("/clues/{clue_id}")
async def delete_clue(
    clue_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """删除线索（软删除 - 标记为无效状态）"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        res = (
            await client.table("business_clue")
            .update({
                "status": "invalid",
                "updated_by": user_id,
                "updated_at": datetime.now(UTC).isoformat(),
            })
            .eq("id", clue_id)
            .eq("tenant_id", org_id)
            .execute()
        )
        if not res.data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "线索不存在")

        return api_success(message="线索已删除")
    except Exception as e:
        logger.error(f"Delete clue error: id={clue_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---------------------------------------------------------------------------
# Follow-up endpoint
# ---------------------------------------------------------------------------


@router.post("/clues/{clue_id}/follow-up")
async def add_follow_up(
    clue_id: str,
    body: FollowUpRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """添加线索跟进记录"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        follow_up_data = {
            "follow_type": body.action,
            "content": body.content,
            "next_action": body.next_action,
            "next_action_date": body.next_action_date,
        }

        result = await clue_service.add_follow_up(
            tenant_id=org_id,
            clue_id=clue_id,
            user_id=user_id,
            data=follow_up_data,
            db=client,
        )

        return api_success(data={"follow_up": result}, message="跟进记录已添加")
    except Exception as e:
        logger.error(f"Add follow-up error: clue={clue_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---------------------------------------------------------------------------
# Clue conversion endpoint
# ---------------------------------------------------------------------------


@router.post("/clues/{clue_id}/convert")
async def convert_clue(
    clue_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """将线索转化为CRM客户"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        # Get clue first to verify existence
        clue = await clue_service.get_clue(
            tenant_id=org_id,
            clue_id=clue_id,
            db=client,
        )
        if not clue:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "线索不存在")

        if clue.get("status") == "converted":
            return api_error(ErrorCode.RESOURCE_CONFLICT, "该线索已转化")

        # Build customer data from clue
        customer_data = {
            "id": str(uuid.uuid4()),
            "org_id": org_id,
            "customer_name": clue.get("title", ""),
            "contact_name": clue.get("contact_name", ""),
            "contact_phone": clue.get("contact_phone", ""),
            "contact_email": clue.get("contact_email", ""),
            "source": clue.get("source", "clue_conversion"),
            "industry": clue.get("industry", ""),
            "region": clue.get("region", ""),
            "clue_id": clue_id,
            "created_by": user_id,
            "created_at": datetime.now(UTC).isoformat(),
        }

        # Insert into customers table
        cust_res = await client.table("customers").insert(customer_data).execute()
        customer = cust_res.data[0] if cust_res.data else customer_data

        # Update clue status to converted
        await (
            client.table("business_clue")
            .update({
                "status": "converted",
                "updated_by": user_id,
                "updated_at": datetime.now(UTC).isoformat(),
            })
            .eq("id", clue_id)
            .eq("tenant_id", org_id)
            .execute()
        )

        return api_success(
            data={"customer": customer, "clue_id": clue_id},
            message="线索已成功转化为客户",
        )
    except Exception as e:
        logger.error(f"Convert clue error: clue={clue_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
