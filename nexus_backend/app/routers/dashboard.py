"""
Dashboard Router — boss-level analytics and summaries.

Extracted from main.py to follow single-responsibility principle.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/boss")
async def boss_dashboard(request: Request, user_id: str = Depends(get_current_user_id)):
    """
    Boss dashboard — pending approvals, abnormal expenses, top performers.

    Requires authentication AND boss role.
    Uses request.state.db for RLS-scoped access.
    """
    client = request.state.db

    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "Database connection unavailable")

    try:
        # Verify user has boss role
        user_res = await client.table("users").select("role").eq("id", user_id).single().execute()

        if not user_res.data or user_res.data.get("role") != "boss":
            raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "仅领导可访问此仪表板")

        # 1. Pending Approvals Count
        pending_res = (
            await client.table("approval_requests").select("count", count="exact").eq("status", "pending").execute()
        )
        pending_count = pending_res.count if pending_res.count is not None else 0

        # 2. Abnormal Expenses (high amount pending)
        abnormal_res = (
            await client.table("approval_requests")
            .select("id, description, amount, users:submitted_by(name)")
            .eq("status", "pending")
            .eq("type", "expense")
            .gt("amount", 1000)
            .order("amount", desc=True)
            .limit(5)
            .execute()
        )

        abnormal_expenses = []
        for item in abnormal_res.data:
            user_name = "Unknown"
            if item.get("users"):
                user_name = item["users"].get("name", "Unknown")

            abnormal_expenses.append(
                {
                    "id": item["id"],
                    "user": user_name,
                    "amount": item["amount"],
                    "reason": item.get("description", "No description"),
                }
            )

        # 3. Top Performers
        users_res = (
            await client.table("users").select("name, score, total_bonus").order("score", desc=True).limit(3).execute()
        )

        top_performers = [u["name"] for u in users_res.data]

        return api_success(
            data={
                "pending_approvals": pending_count,
                "abnormal_expenses": abnormal_expenses,
                "top_performers": top_performers,
                "system_status": "Healthy",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching boss dashboard data: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
