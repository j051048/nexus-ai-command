"""库存管理 API 路由"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.inventory_service import inventory_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/inventory", tags=["Inventory"])


# ── Schemas ──


class InventoryInBody(BaseModel):
    item_id: str
    quantity: int
    reason: str | None = None


class InventoryOutBody(BaseModel):
    item_id: str
    quantity: int
    receiver_id: str | None = None
    reason: str | None = None


# ── Endpoints ──


@router.get("")
async def list_inventory(
    req: Request,
    category: str = None,
    location: str = None,
    search: str = None,
    low_stock_only: bool = None,
    user_id: str = Depends(get_current_user_id),
):
    """查询库存列表"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        filters = {}
        if category:
            filters["category"] = category
        if location:
            filters["location"] = location
        if search:
            filters["search"] = search
        if low_stock_only is not None:
            filters["low_stock_only"] = low_stock_only
        items = await inventory_service.list_inventory(
            org_id=org_id, filters=filters if filters else None, db=db,
        )
        return api_success(data={"items": items})
    except Exception as e:
        logger.error(f"Failed to list inventory: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/in")
async def inventory_in(
    body: InventoryInBody,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """入库"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        result = await inventory_service.inventory_in(
            org_id=org_id,
            item_id=body.item_id,
            quantity=body.quantity,
            operator_id=user_id,
            reason=body.reason,
            db=db,
        )
        return api_success(data={"record": result}, message="入库成功")
    except Exception as e:
        logger.error(f"Failed to process inventory in: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/out")
async def inventory_out(
    body: InventoryOutBody,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """出库"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        result = await inventory_service.inventory_out(
            org_id=org_id,
            item_id=body.item_id,
            quantity=body.quantity,
            operator_id=user_id,
            receiver_id=body.receiver_id,
            reason=body.reason,
            db=db,
        )
        return api_success(data={"record": result}, message="出库成功")
    except Exception as e:
        logger.error(f"Failed to process inventory out: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/alerts")
async def low_stock_alert(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """低库存预警"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        alerts = await inventory_service.get_low_stock_items(org_id=org_id, db=db)
        return api_success(data={"alerts": alerts})
    except Exception as e:
        logger.error(f"Failed to get low stock alerts: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/statistics")
async def inventory_statistics(
    req: Request,
    category: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """库存统计"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        stats = await inventory_service.get_inventory_statistics(
            org_id=org_id, category=category, db=db,
        )
        return api_success(data=stats)
    except Exception as e:
        logger.error(f"Failed to get inventory statistics: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
