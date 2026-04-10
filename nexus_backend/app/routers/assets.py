"""资产管理 API 路由"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.asset_service import asset_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assets", tags=["Assets"])


# ── Schemas ──


class AssetCreate(BaseModel):
    asset_code: str
    name: str
    asset_type: str
    department_id: str | None = None
    value: float | None = None
    purchase_date: str | None = None
    metadata: dict | None = None


class AssetUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    department_id: str | None = None
    current_user_id: str | None = None


class AssetTransferRequest(BaseModel):
    transfer_type: str  # allocate/return/transfer/scrap
    to_user_id: str | None = None
    to_department_id: str | None = None
    reason: str | None = None


# ── Endpoints ──


@router.get("")
async def list_assets(
    req: Request,
    asset_type: str = None,
    status: str = None,
    department_id: str = None,
    search: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """查询资产列表"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        filters = {}
        if asset_type:
            filters["asset_type"] = asset_type
        if status:
            filters["status"] = status
        if department_id:
            filters["department_id"] = department_id
        if search:
            filters["search"] = search
        assets = await asset_service.list_assets(
            org_id=org_id,
            filters=filters if filters else None,
            db=db,
        )
        return api_success(data={"assets": assets})
    except Exception as e:
        logger.error(f"Failed to list assets: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "资产操作失败")


@router.get("/statistics")
async def get_asset_statistics(
    req: Request,
    asset_type: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """资产统计"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        stats = await asset_service.get_asset_statistics(
            org_id=org_id,
            asset_type=asset_type,
            db=db,
        )
        return api_success(data=stats)
    except Exception as e:
        logger.error(f"Failed to get asset statistics: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "资产操作失败")


@router.get("/types")
async def list_asset_types(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """查询资产类型"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        types = await asset_service.list_asset_types(org_id=org_id, db=db)
        return api_success(data={"asset_types": types})
    except Exception as e:
        logger.error(f"Failed to list asset types: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "资产操作失败")


@router.get("/{asset_id}")
async def get_asset_detail(
    asset_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取资产详情"""
    try:
        db = getattr(req.state, "db", None)
        asset = await asset_service.get_asset_detail(asset_id=asset_id, db=db)
        if not asset:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "资产不存在")
        return api_success(data={"asset": asset})
    except Exception as e:
        logger.error(f"Failed to get asset detail: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "资产操作失败")


@router.post("")
async def create_asset(
    body: AssetCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建资产"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        data = body.model_dump(exclude_none=True)
        asset = await asset_service.create_asset(org_id=org_id, data=data, db=db)
        return api_success(data={"asset": asset}, message="资产创建成功")
    except Exception as e:
        logger.error(f"Failed to create asset: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "资产操作失败")


@router.patch("/{asset_id}")
async def update_asset(
    asset_id: str,
    body: AssetUpdate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新资产"""
    try:
        db = getattr(req.state, "db", None)
        updates = body.model_dump(exclude_none=True)
        if not updates:
            raise api_error(
                ErrorCode.VALIDATION_MISSING_FIELD, "请提供至少一个要更新的字段"
            )
        asset = await asset_service.update_asset(
            asset_id=asset_id, updates=updates, db=db
        )
        return api_success(data={"asset": asset}, message="资产更新成功")
    except Exception as e:
        logger.error(f"Failed to update asset: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "资产操作失败")


@router.post("/{asset_id}/transfer")
async def transfer_asset(
    asset_id: str,
    body: AssetTransferRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """资产转移/领用/归还"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)

        # 获取当前资产信息
        asset = await asset_service.get_asset_detail(asset_id=asset_id, db=db)
        if not asset:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "资产不存在")

        result = await asset_service.transfer_asset(
            org_id=org_id,
            asset_id=asset_id,
            transfer_type=body.transfer_type,
            operator_id=user_id,
            from_user_id=asset.get("current_user_id"),
            to_user_id=body.to_user_id,
            from_department_id=asset.get("department_id"),
            to_department_id=body.to_department_id,
            reason=body.reason,
            db=db,
        )
        return api_success(data={"transfer": result}, message="资产转移成功")
    except Exception as e:
        logger.error(f"Failed to transfer asset: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "资产操作失败")
