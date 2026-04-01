"""OA办公 - 请假和会议预订 API 路由"""

import logging
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/oa", tags=["OA"])


class LeaveRequestCreate(BaseModel):
    leave_type: str
    start_date: str
    end_date: str
    reason: str | None = None


class MeetingBookingCreate(BaseModel):
    title: str
    room: str
    start_time: str
    end_time: str
    attendees: list[str] | None = None


@router.get("/leave-requests")
async def list_leave_requests(
    req: Request,
    status: str | None = None,
    user_id: str = Depends(get_current_user_id),
):
    """获取请假申请列表"""
    try:
        org_id = getattr(req.state, "org_id", None)
        db = getattr(req.state, "db", None)

        query = db.table("oa_leave_requests").select("*")
        if org_id:
            query = query.eq("tenant_id", org_id)
        if status:
            query = query.eq("status", status)

        result = await query.execute()
        return api_success(data={"requests": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list leave requests: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取请假申请失败")
