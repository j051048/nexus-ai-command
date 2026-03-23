"""审批流程 API 路由"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.approval_flow_service import approval_flow_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/approval-flows", tags=["Approval Flows"])


# ── Schemas ──


class ApprovalFlowCreate(BaseModel):
    name: str
    trigger_type: str
    steps: list[dict[str, Any]]
    conditions: dict[str, Any] | None = None


# ── Endpoints ──


@router.get("")
async def list_approval_flows(
    req: Request,
    trigger_type: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """查询审批流程列表"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        flows = await approval_flow_service.list_approval_flows(
            org_id=org_id,
            trigger_type=trigger_type,
            db=db,
        )
        return api_success(data={"approval_flows": flows})
    except Exception as e:
        logger.error(f"Failed to list approval flows: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "审批流程操作失败")


@router.post("")
async def create_approval_flow(
    body: ApprovalFlowCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建审批流程"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        flow = await approval_flow_service.create_approval_flow(
            org_id=org_id,
            name=body.name,
            trigger_type=body.trigger_type,
            steps=body.steps,
            conditions=body.conditions,
            db=db,
        )
        return api_success(data={"approval_flow": flow}, message="审批流程创建成功")
    except Exception as e:
        logger.error(f"Failed to create approval flow: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "审批流程操作失败")
