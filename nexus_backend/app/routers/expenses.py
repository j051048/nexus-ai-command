"""费用报销 API 路由"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.expense_service import expense_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/expenses", tags=["Expenses"])


# ── Schemas ──


class ExpenseSubmit(BaseModel):
    employee_id: str
    expense_type: str
    total_amount: float
    items: list[dict[str, Any]] = []


class ExpenseApprove(BaseModel):
    action: str
    comment: str | None = None


# ── Endpoints ──


@router.post("")
async def submit_expense(
    body: ExpenseSubmit,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """提交报销申请"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        expense = await expense_service.submit_expense(
            org_id=org_id,
            employee_id=body.employee_id,
            expense_type=body.expense_type,
            total_amount=body.total_amount,
            items=body.items or None,
            db=db,
        )
        return api_success(data={"expense": expense}, message="报销申请已提交")
    except Exception as e:
        logger.error(f"Failed to submit expense: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "费用操作失败")


@router.get("")
async def list_expenses(
    req: Request,
    status: str = None,
    start_date: str = None,
    end_date: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """查询报销列表"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        filters = {}
        if status:
            filters["status"] = status
        if start_date:
            filters["start_date"] = start_date
        if end_date:
            filters["end_date"] = end_date
        expenses = await expense_service.list_expenses(
            org_id=org_id,
            filters=filters if filters else None,
            db=db,
        )
        return api_success(data={"expenses": expenses})
    except Exception as e:
        logger.error(f"Failed to list expenses: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "费用操作失败")


@router.patch("/{expense_id}/approve")
async def approve_expense(
    expense_id: str,
    body: ExpenseApprove,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """审批报销"""
    try:
        db = getattr(req.state, "db", None)
        result = await expense_service.approve_expense(
            expense_id=expense_id,
            action=body.action,
            comment=body.comment,
            db=db,
        )
        return api_success(data={"expense": result}, message="审批完成")
    except Exception as e:
        logger.error(f"Failed to approve expense: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "费用操作失败")


@router.get("/statistics")
async def expense_statistics(
    req: Request,
    start_date: str = None,
    end_date: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """费用统计"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        filters = {}
        if start_date:
            filters["start_date"] = start_date
        if end_date:
            filters["end_date"] = end_date
        stats = await expense_service.get_expense_statistics(
            org_id=org_id,
            filters=filters if filters else None,
            db=db,
        )
        return api_success(data=stats)
    except Exception as e:
        logger.error(f"Failed to get expense statistics: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "费用操作失败")


@router.get("/budget")
async def budget_check(
    req: Request,
    department_id: str = None,
    period: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """预算检查"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        result = await expense_service.check_budget(
            org_id=org_id,
            department_id=department_id,
            period=period,
            db=db,
        )
        return api_success(data=result)
    except Exception as e:
        logger.error(f"Failed to check budget: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "费用操作失败")
