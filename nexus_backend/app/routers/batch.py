"""
批量操作路由
"""
import logging
from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import get_current_user_id, get_current_org_id
from app.core.errors import api_success, api_error, ErrorCode
from app.tools.batch_operation_tools import (
    batch_import_customers,
    batch_update_leads,
    batch_assign_leads,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/batch", tags=["batch"])


class BatchImportRequest(BaseModel):
    data: list[dict[str, Any]]


class BatchUpdateRequest(BaseModel):
    lead_ids: list[str]
    updates: dict[str, Any]


class BatchAssignRequest(BaseModel):
    lead_ids: list[str]
    owner_id: str


@router.post("/import-customers")
async def import_customers(
    request: BatchImportRequest,
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    """批量导入客户"""
    try:
        result = await batch_import_customers(
            data=request.data, org_id=org_id, user_id=user_id
        )
        return api_success(result) if result.get("success") else api_error(result.get("error"))
    except Exception as e:
        logger.error(f"批量导入失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "批量导入失败，请稍后重试")


@router.post("/update-leads")
async def update_leads(
    request: BatchUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    """批量更新线索"""
    try:
        result = await batch_update_leads(
            lead_ids=request.lead_ids, updates=request.updates, org_id=org_id
        )
        return api_success(result) if result.get("success") else api_error(result.get("error"))
    except Exception as e:
        logger.error(f"批量更新失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "批量更新失败，请稍后重试")


@router.post("/assign-leads")
async def assign_leads(
    request: BatchAssignRequest,
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    """批量分配线索"""
    try:
        result = await batch_assign_leads(
            lead_ids=request.lead_ids, owner_id=request.owner_id, org_id=org_id
        )
        return api_success(result) if result.get("success") else api_error(result.get("error"))
    except Exception as e:
        logger.error(f"批量分配失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "批量分配失败，请稍后重试")
