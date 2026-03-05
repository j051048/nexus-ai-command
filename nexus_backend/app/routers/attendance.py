"""考勤管理 API 路由"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.attendance_service import attendance_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/attendance", tags=["Attendance"])


# ── Schemas ──


class ClockBody(BaseModel):
    clock_type: str
    employee_id: str
    location: Optional[str] = None
    device_info: Optional[str] = None


class ShiftScheduleCreate(BaseModel):
    employee_id: str
    shift_date: str
    shift_type_id: str


class LeaveRequestBody(BaseModel):
    employee_id: str
    leave_type: str
    start_date: str
    end_date: str
    days: float = 1
    reason: Optional[str] = None


# ── Endpoints ──


@router.post("/clock")
async def clock_in_out(
    body: ClockBody,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """打卡签到/签退"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        result = await attendance_service.clock_in_out(
            org_id=org_id,
            employee_id=body.employee_id,
            clock_type=body.clock_type,
            location=body.location,
            device_info=body.device_info,
            db=db,
        )
        return api_success(data={"clock": result}, message="打卡成功")
    except Exception as e:
        logger.error(f"Failed to clock in/out: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/records")
async def get_attendance_records(
    req: Request,
    employee_id: str = None,
    start_date: str = None,
    end_date: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """查询考勤记录"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        records = await attendance_service.get_attendance_records(
            org_id=org_id,
            employee_id=employee_id,
            start_date=start_date,
            end_date=end_date,
            db=db,
        )
        return api_success(data={"records": records})
    except Exception as e:
        logger.error(f"Failed to get attendance records: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/shifts")
async def create_shift_schedule(
    body: ShiftScheduleCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建排班"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        shift = await attendance_service.create_shift_schedule(
            org_id=org_id,
            employee_id=body.employee_id,
            shift_date=body.shift_date,
            shift_type_id=body.shift_type_id,
            created_by=user_id,
            db=db,
        )
        return api_success(data={"shift": shift}, message="排班创建成功")
    except Exception as e:
        logger.error(f"Failed to create shift schedule: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/shifts")
async def list_shift_schedules(
    req: Request,
    department_id: str = None,
    start_date: str = None,
    end_date: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """查询排班列表"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        shifts = await attendance_service.list_shift_schedules(
            org_id=org_id,
            department_id=department_id,
            start_date=start_date,
            end_date=end_date,
            db=db,
        )
        return api_success(data={"shifts": shifts})
    except Exception as e:
        logger.error(f"Failed to list shift schedules: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/statistics")
async def attendance_statistics(
    req: Request,
    department_id: str = None,
    start_date: str = None,
    end_date: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """考勤统计"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        stats = await attendance_service.get_attendance_statistics(
            org_id=org_id,
            department_id=department_id,
            start_date=start_date,
            end_date=end_date,
            db=db,
        )
        return api_success(data=stats)
    except Exception as e:
        logger.error(f"Failed to get attendance statistics: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/leave")
async def request_leave(
    body: LeaveRequestBody,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """请假申请"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        leave = await attendance_service.request_leave(
            org_id=org_id,
            employee_id=body.employee_id,
            leave_type=body.leave_type,
            start_date=body.start_date,
            end_date=body.end_date,
            days=body.days,
            reason=body.reason,
            db=db,
        )
        return api_success(data={"leave": leave}, message="请假申请已提交")
    except Exception as e:
        logger.error(f"Failed to request leave: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
