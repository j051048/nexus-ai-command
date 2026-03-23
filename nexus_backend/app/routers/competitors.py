"""竞品管理 API 端点"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.competitor_service import competitor_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/competitors", tags=["Competitors"])


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------


class CreateCompetitorRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="竞品公司名称")
    brand_names: list[str] | None = Field(None, description="品牌名/别名")
    industry: str | None = Field(None, max_length=100)
    tag: str | None = Field(None, max_length=50)
    logo_url: str | None = Field(None, max_length=500)
    website: str | None = Field(None, max_length=500)
    description: str | None = None
    strength_summary: str | None = None
    weakness_summary: str | None = None
    threat_level: str | None = Field("medium")
    sort_order: int | None = Field(0)


class UpdateCompetitorRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    brand_names: list[str] | None = None
    industry: str | None = Field(None, max_length=100)
    tag: str | None = Field(None, max_length=50)
    logo_url: str | None = Field(None, max_length=500)
    website: str | None = Field(None, max_length=500)
    description: str | None = None
    strength_summary: str | None = None
    weakness_summary: str | None = None
    threat_level: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class CreateProductRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="产品名称")
    model: str | None = Field(None, max_length=100)
    category: str | None = Field(None, max_length=100)
    price_range: str | None = Field(None, max_length=100)
    description: str | None = None
    specs: dict | None = None
    our_competing_product: str | None = Field(None, max_length=200)
    comparison_notes: str | None = None


class UpdateProductRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    model: str | None = Field(None, max_length=100)
    category: str | None = Field(None, max_length=100)
    price_range: str | None = Field(None, max_length=100)
    description: str | None = None
    specs: dict | None = None
    our_competing_product: str | None = Field(None, max_length=200)
    comparison_notes: str | None = None


class UpsertFeatureRequest(BaseModel):
    id: str | None = None
    dimension: str = Field(..., min_length=1, max_length=100, description="对比维度名")
    competitor_score: int | None = Field(None, ge=1, le=10)
    our_score: int | None = Field(None, ge=1, le=10)
    competitor_detail: str | None = None
    our_advantage: str | None = None
    counter_strategy: str | None = None


class LinkDocumentRequest(BaseModel):
    document_id: str = Field(..., description="文档 ID")
    doc_type: str | None = Field("general", max_length=50)


# ---------------------------------------------------------------------------
# Helper: check admin role
# ---------------------------------------------------------------------------


def _check_admin(req: Request):
    """Check user role is founder/boss/manager; raise if not."""
    role = getattr(req.state, "user_role", None)
    if role not in ("founder", "boss", "manager"):
        raise api_error(ErrorCode.FORBIDDEN, "仅管理员可执行此操作")


# ---------------------------------------------------------------------------
# Competitor CRUD
# ---------------------------------------------------------------------------


@router.get("")
async def list_competitors(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """列出本组织所有竞品"""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未找到组织信息")
    try:
        data = await competitor_service.list_competitors(org_id, db=req.state.db)
        return api_success(data=data)
    except Exception as e:
        logger.error(f"List competitors failed: {e}")
        raise api_error(ErrorCode.SERVER_ERROR, "获取竞品列表失败")


@router.post("")
async def create_competitor(
    req: Request,
    body: CreateCompetitorRequest,
    user_id: str = Depends(get_current_user_id),
):
    """创建竞品（需管理员权限）"""
    _check_admin(req)
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未找到组织信息")
    try:
        data = await competitor_service.create_competitor(
            org_id, user_id, body.model_dump(exclude_none=True), db=req.state.db
        )
        return api_success(data=data, message="竞品创建成功")
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "竞品分析参数校验失败")
    except Exception as e:
        logger.error(f"Create competitor failed: {e}")
        raise api_error(ErrorCode.SERVER_ERROR, "创建竞品失败")


@router.get("/{competitor_id}")
async def get_competitor(
    req: Request,
    competitor_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """获取竞品详情（含产品和维度）"""
    try:
        data = await competitor_service.get_battlecard_data(competitor_id, db=req.state.db)
        if not data:
            raise api_error(ErrorCode.NOT_FOUND, "竞品不存在")
        return api_success(data=data)
    except Exception as e:
        if "竞品不存在" in str(e):
            raise
        logger.error(f"Get competitor failed: {e}")
        raise api_error(ErrorCode.SERVER_ERROR, "获取竞品详情失败")


@router.put("/{competitor_id}")
async def update_competitor(
    req: Request,
    competitor_id: str,
    body: UpdateCompetitorRequest,
    user_id: str = Depends(get_current_user_id),
):
    """更新竞品信息（需管理员权限）"""
    _check_admin(req)
    try:
        data = await competitor_service.update_competitor(
            competitor_id, body.model_dump(exclude_none=True), db=req.state.db
        )
        return api_success(data=data, message="竞品更新成功")
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "竞品分析参数校验失败")
    except Exception as e:
        logger.error(f"Update competitor failed: {e}")
        raise api_error(ErrorCode.SERVER_ERROR, "更新竞品失败")


@router.delete("/{competitor_id}")
async def delete_competitor(
    req: Request,
    competitor_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """删除竞品（需管理员权限）"""
    _check_admin(req)
    try:
        await competitor_service.delete_competitor(competitor_id, db=req.state.db)
        return api_success(None, message="竞品已删除")
    except Exception as e:
        logger.error(f"Delete competitor failed: {e}")
        raise api_error(ErrorCode.SERVER_ERROR, "删除竞品失败")


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


@router.get("/{competitor_id}/products")
async def list_products(
    req: Request,
    competitor_id: str,
    user_id: str = Depends(get_current_user_id),
):
    try:
        data = await competitor_service.list_products(competitor_id, db=req.state.db)
        return api_success(data=data)
    except Exception as e:
        logger.error(f"List products failed: {e}")
        raise api_error(ErrorCode.SERVER_ERROR, "竞品分析操作失败")


@router.post("/{competitor_id}/products")
async def create_product(
    req: Request,
    competitor_id: str,
    body: CreateProductRequest,
    user_id: str = Depends(get_current_user_id),
):
    _check_admin(req)
    org_id = getattr(req.state, "org_id", None)
    try:
        data = await competitor_service.create_product(
            competitor_id, org_id, body.model_dump(exclude_none=True), db=req.state.db
        )
        return api_success(data=data, message="产品添加成功")
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "竞品分析参数校验失败")
    except Exception as e:
        logger.error(f"Create product failed: {e}")
        raise api_error(ErrorCode.SERVER_ERROR, "竞品分析操作失败")


@router.put("/{competitor_id}/products/{product_id}")
async def update_product(
    req: Request,
    competitor_id: str,
    product_id: str,
    body: UpdateProductRequest,
    user_id: str = Depends(get_current_user_id),
):
    _check_admin(req)
    try:
        data = await competitor_service.update_product(product_id, body.model_dump(exclude_none=True), db=req.state.db)
        return api_success(data=data, message="产品更新成功")
    except Exception as e:
        logger.error(f"Update product failed: {e}")
        raise api_error(ErrorCode.SERVER_ERROR, "竞品分析操作失败")


@router.delete("/{competitor_id}/products/{product_id}")
async def delete_product(
    req: Request,
    competitor_id: str,
    product_id: str,
    user_id: str = Depends(get_current_user_id),
):
    _check_admin(req)
    try:
        await competitor_service.delete_product(product_id, db=req.state.db)
        return api_success(None, message="产品已删除")
    except Exception as e:
        logger.error(f"Delete product failed: {e}")
        raise api_error(ErrorCode.SERVER_ERROR, "竞品分析操作失败")


# ---------------------------------------------------------------------------
# Features (comparison dimensions)
# ---------------------------------------------------------------------------


@router.get("/{competitor_id}/features")
async def list_features(
    req: Request,
    competitor_id: str,
    user_id: str = Depends(get_current_user_id),
):
    try:
        data = await competitor_service.list_features(competitor_id, db=req.state.db)
        return api_success(data=data)
    except Exception as e:
        logger.error(f"List features failed: {e}")
        raise api_error(ErrorCode.SERVER_ERROR, "竞品分析操作失败")


@router.post("/{competitor_id}/features")
async def upsert_feature(
    req: Request,
    competitor_id: str,
    body: UpsertFeatureRequest,
    user_id: str = Depends(get_current_user_id),
):
    _check_admin(req)
    org_id = getattr(req.state, "org_id", None)
    try:
        data = await competitor_service.upsert_feature(
            competitor_id, org_id, body.model_dump(exclude_none=True), db=req.state.db
        )
        return api_success(data=data, message="对比维度保存成功")
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "竞品分析参数校验失败")
    except Exception as e:
        logger.error(f"Upsert feature failed: {e}")
        raise api_error(ErrorCode.SERVER_ERROR, "竞品分析操作失败")


@router.delete("/{competitor_id}/features/{feature_id}")
async def delete_feature(
    req: Request,
    competitor_id: str,
    feature_id: str,
    user_id: str = Depends(get_current_user_id),
):
    _check_admin(req)
    try:
        await competitor_service.delete_feature(feature_id, db=req.state.db)
        return api_success(None, message="对比维度已删除")
    except Exception as e:
        logger.error(f"Delete feature failed: {e}")
        raise api_error(ErrorCode.SERVER_ERROR, "竞品分析操作失败")


# ---------------------------------------------------------------------------
# Document linking
# ---------------------------------------------------------------------------


@router.get("/{competitor_id}/documents")
async def list_documents(
    req: Request,
    competitor_id: str,
    user_id: str = Depends(get_current_user_id),
):
    try:
        data = await competitor_service.list_documents(competitor_id, db=req.state.db)
        return api_success(data=data)
    except Exception as e:
        logger.error(f"List documents failed: {e}")
        raise api_error(ErrorCode.SERVER_ERROR, "竞品分析操作失败")


@router.post("/{competitor_id}/documents")
async def link_document(
    req: Request,
    competitor_id: str,
    body: LinkDocumentRequest,
    user_id: str = Depends(get_current_user_id),
):
    _check_admin(req)
    try:
        await competitor_service.link_document(
            competitor_id, body.document_id, body.doc_type or "general", db=req.state.db
        )
        return api_success(None, message="文档关联成功")
    except Exception as e:
        logger.error(f"Link document failed: {e}")
        raise api_error(ErrorCode.SERVER_ERROR, "竞品分析操作失败")


@router.delete("/{competitor_id}/documents/{document_id}")
async def unlink_document(
    req: Request,
    competitor_id: str,
    document_id: str,
    user_id: str = Depends(get_current_user_id),
):
    _check_admin(req)
    try:
        await competitor_service.unlink_document(competitor_id, document_id, db=req.state.db)
        return api_success(None, message="文档关联已移除")
    except Exception as e:
        logger.error(f"Unlink document failed: {e}")
        raise api_error(ErrorCode.SERVER_ERROR, "竞品分析操作失败")
