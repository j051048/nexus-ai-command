"""OA办公 - 请假、会议预订和任务 API 路由"""

import logging

from fastapi import APIRouter, Depends, Query, Request
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
    db = getattr(req.state, "db", None)
    if not db:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

    today = date.today().isoformat()
    try:
        result = await db.table("attendance_records").select("*").eq("user_id", user_id).eq("check_date", today).execute()
        return api_success(data={"records": result.data or []})
    except Exception as e:
        logger.error(f"Failed to fetch today's attendance: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取打卡记录失败")


@router.post("/attendance/clock")
async def clock_attendance(req: Request, user_id: str = Depends(get_current_user_id)):
    """打卡（上班/下班/外勤）"""
    from datetime import date, datetime
    db = getattr(req.state, "db", None)
    if not db:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

    try:
        body = await req.json()
        clock_type = body.get("clock_type")
        org_id = getattr(req.state, "org_id", body.get("organization_id"))
        if not org_id:
            raise api_error(ErrorCode.VALIDATION_MISSING_FIELD, "组织ID缺失")

        today = date.today().isoformat()
        now_time = datetime.now().isoformat()

        # Fix #1: Correct method name 'maybe_single()'
        existing = await db.table("attendance_records").select("id, check_in_time").eq("user_id", user_id).eq("check_date", today).maybe_single().execute()

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
            record = {
                "user_id": user_id,
                "organization_id": org_id,
                "platform": "wecom",
                "check_date": today
            }
            if clock_type == "clock_in":
                record["check_in_time"] = now_time
            elif clock_type == "clock_out":
                record["check_out_time"] = now_time
            elif clock_type == "field_work":
                record["check_in_time"] = now_time
                record["location"] = "外勤"
            await db.table("attendance_records").insert(record).execute()

        return api_success({}, message="打卡成功")
    except Exception as e:
        logger.error(f"Attendance clock failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, f"打卡失败: {str(e)}")


@router.get("/leave-requests")
async def list_leave_requests(
    req: Request,
    status: str | None = None,
    user_id: str = Depends(get_current_user_id),
):
    """获取请假申请列表"""
    try:
        getattr(req.state, "org_id", None)
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        query = db.table("oa_leave_requests").select("*")
        if status:
            query = query.eq("status", status)

        result = await query.execute()
        return api_success(data={"requests": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list leave requests: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取请假申请失败")


@router.post("/leave-request")
async def create_leave_request(
    request_data: LeaveRequestCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建请假申请"""
    try:
        db = getattr(req.state, "db", None)
        org_id = getattr(req.state, "org_id", None)
        if not db or not org_id:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "上下文数据缺失")

        leave_data = request_data.model_dump()
        leave_data["user_id"] = user_id
        leave_data["status"] = "pending"

        result = await db.table("oa_leave_requests").insert(leave_data).execute()
        return api_success(data={"request": result.data[0] if result.data else {}})
    except Exception as e:
        logger.error(f"Failed to create leave request: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "提交请假申请失败")


# ── Pydantic Models ─────────────────────────────────────────────────────


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    priority: str = "medium"
    assignee_id: str | None = None
    due_date: str | None = None


class TaskUpdate(BaseModel):
    status: str | None = None
    assignee_id: str | None = None


# ── 会议管理 ────────────────────────────────────────────────────────────


@router.get("/meetings")
async def list_meetings(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取会议列表"""
    try:
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

        result = await db.table("oa_meeting_bookings").select("*").order("start_time", desc=True).execute()
        return api_success(data={"meetings": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list meetings: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取会议列表失败")


@router.post("/meetings")
async def create_meeting(
    body: MeetingBookingCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建会议预订"""
    try:
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

        data = body.model_dump()
        data["user_id"] = user_id
        data["status"] = "confirmed"

        result = await db.table("oa_meeting_bookings").insert(data).execute()
        return api_success(data={"meeting": result.data[0] if result.data else {}})
    except Exception as e:
        logger.error(f"Failed to create meeting: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "创建会议失败")


@router.patch("/meetings/{meeting_id}/cancel")
async def cancel_meeting(
    meeting_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """取消会议"""
    try:
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

        await db.table("oa_meeting_bookings").update({"status": "cancelled"}).eq("id", meeting_id).execute()
        return api_success(data={"cancelled": True})
    except Exception as e:
        logger.error(f"Failed to cancel meeting: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "取消会议失败")


# ── OA 任务管理 ─────────────────────────────────────────────────────────


@router.get("/tasks")
async def list_oa_tasks(
    req: Request,
    assignee_id: str | None = Query(None),
    user_id: str = Depends(get_current_user_id),
):
    """获取OA任务列表"""
    try:
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

        query = db.table("oa_tasks").select("*")
        if assignee_id:
            query = query.eq("assignee_id", assignee_id)
        result = await query.order("created_at", desc=True).execute()
        return api_success(data={"tasks": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list OA tasks: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取任务列表失败")


@router.post("/tasks")
async def create_oa_task(
    body: TaskCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建OA任务"""
    try:
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

        data = body.model_dump()
        data["created_by"] = user_id
        data["status"] = "pending"

        result = await db.table("oa_tasks").insert(data).execute()
        return api_success(data={"task": result.data[0] if result.data else {}})
    except Exception as e:
        logger.error(f"Failed to create OA task: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "创建任务失败")


@router.patch("/tasks/{task_id}")
async def update_oa_task(
    task_id: str,
    body: TaskUpdate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新OA任务（状态、指派人等）"""
    try:
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

        updates = body.model_dump(exclude_none=True)
        if not updates:
            raise api_error(ErrorCode.VALIDATION_MISSING_FIELD, "无可更新字段")

        result = await db.table("oa_tasks").update(updates).eq("id", task_id).execute()
        return api_success(data={"task": result.data[0] if result.data else {}})
    except Exception as e:
        logger.error(f"Failed to update OA task: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "更新任务失败")


# ── 请假审批 ────────────────────────────────────────────────────────────


@router.patch("/leave-requests/{request_id}")
async def approve_leave_request(
    request_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """审批请假申请（approve/reject）"""
    try:
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

        body = await req.json()
        status = body.get("status")
        if status not in ("approved", "rejected"):
            raise api_error(ErrorCode.VALIDATION_MISSING_FIELD, "status 必须为 approved 或 rejected")

        await db.table("oa_leave_requests").update({"status": status}).eq("id", request_id).execute()
        return api_success(data={"updated": True})
    except Exception as e:
        logger.error(f"Failed to approve/reject leave request: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "审批请假申请失败")
