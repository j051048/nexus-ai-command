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


@router.get("/attendance/today")
async def get_today_attendance(req: Request, user_id: str = Depends(get_current_user_id)):
    """获取今日打卡记录"""
    from datetime import date
    db = req.state.db
    today = date.today().isoformat()
    result = await db.table("attendance_records").select("*").eq("user_id", user_id).eq("check_date", today).execute()
    return api_success(data={"records": result.data or []})


@router.post("/attendance/clock")
async def clock_attendance(req: Request, user_id: str = Depends(get_current_user_id)):
    """打卡（上班/下班/外勤）"""
    from datetime import date, datetime
    db = req.state.db
    body = await req.json()
    clock_type = body.get("clock_type")
    org_id = body.get("organization_id")
    today = date.today().isoformat()
    now_time = datetime.now().isoformat()

    existing = await db.table("attendance_records").select("id, check_in_time").eq("user_id", user_id).eq("check_date", today).maybeSingle().execute()

    if existing.data:
        updates = {}
        if clock_type == "clock_in":
            updates["check_in_time"] = now_time
        elif clock_type == "clock_out":
            updates["check_out_time"] = now_time
        elif clock_type == "field_work":
            updates["location"] = "外勤"
            if not existing.data.get("check_in_time"):
                updates["check_in_time"] = now_time
        await db.table("attendance_records").update(updates).eq("id", existing.data["id"]).execute()
    else:
        record = {"user_id": user_id, "organization_id": org_id, "platform": "wecom", "check_date": today}
        if clock_type == "clock_in":
            record["check_in_time"] = now_time
        elif clock_type == "clock_out":
            record["check_out_time"] = now_time
        elif clock_type == "field_work":
            record["check_in_time"] = now_time
            record["location"] = "外勤"
        await db.table("attendance_records").insert(record).execute()

    return api_success(message="打卡成功")


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


@router.post("/leave-request")
async def create_leave_request(req: Request, user_id: str = Depends(get_current_user_id)):
    """创建请假申请"""
    db = req.state.db
    body = await req.json()
    leave_request = {
        "user_id": user_id,
        "organization_id": body.get("organization_id"),
        "leave_type": body.get("leave_type"),
        "start_date": body.get("start_date"),
        "end_date": body.get("end_date"),
        "days": body.get("days", 1),
        "reason": body.get("reason"),
        "status": "pending",
    }
    await db.table("oa_leave_requests").insert(leave_request).execute()
    return api_success(message="请假申请已提交")
