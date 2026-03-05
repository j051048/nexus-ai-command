"""工单系统 API 路由"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.work_order_service import work_order_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/work-orders", tags=["Work Orders"])


# ── Schemas ──


class WorkOrderCreate(BaseModel):
    title: str
    order_type: str
    description: Optional[str] = None
    priority: Optional[str] = "medium"
    assignee_id: Optional[str] = None
    department_id: Optional[str] = None


class WorkOrderUpdate(BaseModel):
    status: Optional[str] = None
    assignee_id: Optional[str] = None
    comment: Optional[str] = None


# ── Endpoints ──


@router.get("")
async def list_work_orders(
    req: Request,
    order_type: str = None,
    status: str = None,
    priority: str = None,
    assignee_id: str = None,
    search: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """查询工单列表"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        filters = {}
        if order_type:
            filters["order_type"] = order_type
        if status:
            filters["status"] = status
        if priority:
            filters["priority"] = priority
        if assignee_id:
            filters["assignee_id"] = assignee_id
        if search:
            filters["search"] = search
        orders = await work_order_service.list_work_orders(
            org_id=org_id, filters=filters if filters else None, db=db,
        )
        return api_success(data={"work_orders": orders})
    except Exception as e:
        logger.error(f"Failed to list work orders: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/statistics")
async def get_statistics(
    req: Request,
    order_type: str = None,
    start_date: str = None,
    end_date: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """工单统计"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        time_range = {}
        if start_date:
            time_range["start_date"] = start_date
        if end_date:
            time_range["end_date"] = end_date
        stats = await work_order_service.get_work_order_statistics(
            org_id=org_id,
            order_type=order_type,
            time_range=time_range if time_range else None,
            db=db,
        )
        return api_success(data=stats)
    except Exception as e:
        logger.error(f"Failed to get work order statistics: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/types")
async def list_types(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """查询工单类型"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        types = await work_order_service.list_work_order_types(org_id=org_id, db=db)
        return api_success(data={"work_order_types": types})
    except Exception as e:
        logger.error(f"Failed to list work order types: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/{order_id}")
async def get_work_order_detail(
    order_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取工单详情"""
    try:
        db = getattr(req.state, "db", None)
        order = await work_order_service.get_work_order_detail(order_id=order_id, db=db)
        if not order:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "工单不存在")

        # 获取评论
        comments = await work_order_service.get_work_order_comments(order_id=order_id, db=db)
        order["comments"] = comments

        return api_success(data={"work_order": order})
    except Exception as e:
        logger.error(f"Failed to get work order detail: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("")
async def create_work_order(
    body: WorkOrderCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建工单"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        data = body.model_dump(exclude_none=True)
        order = await work_order_service.create_work_order(
            org_id=org_id, creator_id=user_id, data=data, db=db,
        )
        return api_success(data={"work_order": order}, message="工单创建成功")
    except Exception as e:
        logger.error(f"Failed to create work order: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.patch("/{order_id}")
async def update_work_order(
    order_id: str,
    body: WorkOrderUpdate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新工单"""
    try:
        db = getattr(req.state, "db", None)
        updates = {}
        if body.status:
            updates["status"] = body.status
            if body.status == "resolved":
                from datetime import UTC, datetime
                updates["resolved_at"] = datetime.now(UTC).isoformat()
        if body.assignee_id:
            updates["assignee_id"] = body.assignee_id

        order = await work_order_service.update_work_order(
            order_id=order_id,
            user_id=user_id,
            updates=updates,
            comment=body.comment,
            db=db,
        )
        return api_success(data={"work_order": order}, message="工单更新成功")
    except Exception as e:
        logger.error(f"Failed to update work order: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
