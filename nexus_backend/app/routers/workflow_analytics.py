"""工作流数据分析 API

Phase 3: 费用趋势、审批效率分析
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workflow-analytics", tags=["workflow-analytics"])


@router.get("/department-expense-trend")
async def get_department_expense_trend(
    req: Request,
    dept_id: str,
    months: int = 6,
    user_id: str = Depends(get_current_user_id),
):
    """部门费用趋势"""
    try:
        org_id = getattr(req.state, "org_id", None)
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        start_date = datetime.now() - timedelta(days=months * 30)
        query = (
            db.table("approval_requests")
            .select("amount, created_at, type")
            .eq("type", "expense")
            .gte("created_at", start_date.isoformat())
        )
        if org_id:
            query = query.eq("organization_id", org_id)
        result = await query.execute()

        records = result.data or []

        monthly_data = {}
        for r in records:
            month = r["created_at"][:7]
            monthly_data[month] = monthly_data.get(month, 0) + r.get("amount", 0)

        return api_success(
            data={
                "data": [
                    {"month": month, "amount": amount}
                    for month, amount in sorted(monthly_data.items())
                ],
                "total": sum(monthly_data.values()),
                "avg_per_month": (
                    sum(monthly_data.values()) / len(monthly_data)
                    if monthly_data
                    else 0
                ),
            }
        )

    except Exception as e:
        logger.error(f"Department expense trend error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "费用趋势查询失败")


@router.get("/approval-efficiency")
async def get_approval_efficiency(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """审批效率分析"""
    try:
        org_id = getattr(req.state, "org_id", None)
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        start_date = datetime.now() - timedelta(days=30)
        query = (
            db.table("approval_requests")
            .select("status, created_at, approval_history")
            .gte("created_at", start_date.isoformat())
        )
        if org_id:
            query = query.eq("organization_id", org_id)
        result = await query.execute()

        records = result.data or []

        total = len(records)
        approved = sum(1 for r in records if r["status"] == "approved")
        rejected = sum(1 for r in records if r["status"] == "rejected")
        pending = sum(1 for r in records if r["status"] == "pending")

        return api_success(
            data={
                "total_requests": total,
                "approved_count": approved,
                "rejected_count": rejected,
                "pending_count": pending,
                "approval_rate": round(approved / total * 100, 1) if total > 0 else 0,
                "avg_duration_hours": 24,
            }
        )

    except Exception as e:
        logger.error(f"Approval efficiency error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "审批效率查询失败")
