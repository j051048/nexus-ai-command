"""
考勤管理工具集
提供打卡、排班、考勤统计、请假等功能
"""

import logging
import uuid as _uuid
from typing import Any

from app.core.database import supabase
from app.services.attendance_service import attendance_service

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


def _get_client(config: dict = None):
    """Get scoped DB client if user token available, else fallback to service client."""
    token = config.get("token") if config else None
    return supabase.get_scoped_client(token) if token and supabase else supabase


def _get_org_id(config: dict = None) -> str | None:
    return config.get("org_id") if config else None


def _validate_uuid(value: str, field_name: str = "ID") -> str | None:
    """验证UUID格式"""
    try:
        _uuid.UUID(value)
        return None
    except (ValueError, TypeError, AttributeError):
        return f"{field_name} '{value}' 不是有效的UUID格式。"


# ============================================================================
# 考勤管理工具
# ============================================================================


class ClockInOutTool(BaseTool):
    """打卡（上班/下班/外勤打卡）"""

    name = "clock_in_out"
    description = (
        "打卡（上班/下班/外勤打卡）。"
        "当用户说'打卡'、'上班签到'、'下班打卡'时调用。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "clock_type": {
                "type": "string",
                "description": "打卡类型",
                "enum": ["clock_in", "clock_out", "field_work"],
            },
            "location": {
                "type": "object",
                "description": "打卡位置信息（可选）",
            },
            "device_info": {
                "type": "object",
                "description": "设备信息（可选）",
            },
        },
        "required": ["clock_type"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        clock_type = args.get("clock_type", "").strip()
        if not clock_type:
            return "❌ 请指定打卡类型（clock_in/clock_out/field_work）"

        # 查找当前用户对应的员工ID
        try:
            emp_resp = client.table("employees").select("id").eq("user_id", user_id).eq("tenant_id", org_id).limit(1).execute()
            if not emp_resp.data:
                return "❌ 未找到您的员工信息，请联系管理员。"
            employee_id = emp_resp.data[0]["id"]
        except Exception as e:
            logger.error(f"查询员工信息失败: {e}")
            return f"❌ 查询员工信息失败: {str(e)}"

        try:
            record = await attendance_service.clock_in_out(
                org_id=org_id,
                employee_id=employee_id,
                clock_type=clock_type,
                location=args.get("location"),
                device_info=args.get("device_info"),
                db=client,
            )

            type_labels = {
                "clock_in": "上班打卡",
                "clock_out": "下班打卡",
                "field_work": "外勤打卡",
            }
            ctype = type_labels.get(clock_type, clock_type)

            return (
                f"✅ {ctype}成功！\n\n"
                f"- 打卡时间: {str(record.get('clock_time', ''))[:19]}\n"
                f"- 打卡类型: {ctype}\n"
                f"- ID: {record['id']}"
            )

        except Exception as e:
            logger.error(f"打卡失败: {e}")
            return f"❌ 打卡失败: {str(e)}"


class GetAttendanceRecordTool(BaseTool):
    """查询考勤记录"""

    name = "get_attendance_record"
    description = (
        "查询考勤记录。"
        "当用户说'查看考勤'、'考勤记录'时调用。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "string",
                "description": "员工ID（可选，不填查自己的）",
            },
            "start_date": {
                "type": "string",
                "description": "开始日期 YYYY-MM-DD（可选）",
            },
            "end_date": {
                "type": "string",
                "description": "结束日期 YYYY-MM-DD（可选）",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        if args.get("employee_id") and (err := _validate_uuid(args["employee_id"], "employee_id")):
            return f"❌ {err}"

        try:
            records = await attendance_service.get_attendance_records(
                org_id=org_id,
                employee_id=args.get("employee_id"),
                start_date=args.get("start_date"),
                end_date=args.get("end_date"),
                db=client,
            )

            if not records:
                return "📋 当前暂无考勤记录。"

            type_labels = {
                "clock_in": "上班",
                "clock_out": "下班",
                "field_work": "外勤",
            }

            lines = [f"📋 共找到 {len(records)} 条考勤记录:\n"]
            for r in records:
                ctype = type_labels.get(r.get("clock_type", ""), r.get("clock_type", ""))
                lines.append(
                    f"- {str(r.get('clock_time', ''))[:16]} | 类型: {ctype} | "
                    f"状态: {r.get('status', '正常')}"
                )

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"查询考勤记录失败: {e}")
            return f"❌ 查询考勤记录失败: {str(e)}"


class CreateShiftScheduleTool(BaseTool):
    """创建排班计划"""

    name = "create_shift_schedule"
    description = (
        "创建排班计划。"
        "当用户说'排班'、'创建班次'时调用。"
    )

    required_role = "admin"

    parameters = {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "string",
                "description": "员工ID",
            },
            "shift_date": {
                "type": "string",
                "description": "排班日期 YYYY-MM-DD",
            },
            "shift_type_id": {
                "type": "string",
                "description": "班次类型ID",
            },
        },
        "required": ["employee_id", "shift_date", "shift_type_id"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        employee_id = args.get("employee_id", "").strip()
        shift_date = args.get("shift_date", "").strip()
        shift_type_id = args.get("shift_type_id", "").strip()

        if not employee_id or not shift_date or not shift_type_id:
            return "❌ 员工ID、排班日期和班次类型不能为空"

        if err := _validate_uuid(employee_id, "employee_id"):
            return f"❌ {err}"
        if err := _validate_uuid(shift_type_id, "shift_type_id"):
            return f"❌ {err}"

        try:
            schedule = await attendance_service.create_shift_schedule(
                org_id=org_id,
                employee_id=employee_id,
                shift_date=shift_date,
                shift_type_id=shift_type_id,
                db=client,
            )

            return (
                f"✅ 排班创建成功！\n\n"
                f"- 员工ID: {employee_id[:8]}...\n"
                f"- 排班日期: {shift_date}\n"
                f"- ID: {schedule['id']}"
            )

        except Exception as e:
            logger.error(f"创建排班失败: {e}")
            return f"❌ 创建排班失败: {str(e)}"


class ListShiftSchedulesTool(BaseTool):
    """查询排班表"""

    name = "list_shift_schedules"
    description = (
        "查询排班表。"
        "当用户说'查看排班'、'排班表'时调用。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "department_id": {
                "type": "string",
                "description": "部门ID（可选）",
            },
            "start_date": {
                "type": "string",
                "description": "开始日期 YYYY-MM-DD（可选）",
            },
            "end_date": {
                "type": "string",
                "description": "结束日期 YYYY-MM-DD（可选）",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        if args.get("department_id") and (err := _validate_uuid(args["department_id"], "department_id")):
            return f"❌ {err}"

        try:
            schedules = await attendance_service.list_shift_schedules(
                org_id=org_id,
                department_id=args.get("department_id"),
                start_date=args.get("start_date"),
                end_date=args.get("end_date"),
                db=client,
            )

            if not schedules:
                return "📋 当前暂无排班记录。"

            lines = [f"📅 共找到 {len(schedules)} 条排班记录:\n"]
            for s in schedules:
                employee_name = s.get("employee", {}).get("name", "未知") if s.get("employee") else "未知"
                lines.append(
                    f"- {s.get('shift_date')} | 员工: {employee_name} | "
                    f"班次: {s.get('shift_type', {}).get('name', '未知') if s.get('shift_type') else '未知'}"
                )

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"查询排班表失败: {e}")
            return f"❌ 查询排班表失败: {str(e)}"


class AttendanceStatisticsTool(BaseTool):
    """考勤统计"""

    name = "attendance_statistics"
    description = (
        "考勤统计。"
        "当用户说'考勤统计'、'出勤率'时调用。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "department_id": {
                "type": "string",
                "description": "部门ID（可选）",
            },
            "start_date": {
                "type": "string",
                "description": "开始日期 YYYY-MM-DD（可选）",
            },
            "end_date": {
                "type": "string",
                "description": "结束日期 YYYY-MM-DD（可选）",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        if args.get("department_id") and (err := _validate_uuid(args["department_id"], "department_id")):
            return f"❌ {err}"

        try:
            stats = await attendance_service.get_attendance_statistics(
                org_id=org_id,
                department_id=args.get("department_id"),
                start_date=args.get("start_date"),
                end_date=args.get("end_date"),
                db=client,
            )

            return (
                f"📊 考勤统计:\n\n"
                f"- 总记录数: {stats.get('total_records', 0)}\n"
                f"- 准时打卡: {stats.get('on_time_count', 0)}\n"
                f"- 迟到: {stats.get('late_count', 0)}\n"
                f"- 早退: {stats.get('early_leave_count', 0)}\n"
                f"- 准时率: {stats.get('on_time_rate', 0)}%"
            )

        except Exception as e:
            logger.error(f"获取考勤统计失败: {e}")
            return f"❌ 获取考勤统计失败: {str(e)}"


class RequestLeaveTool(BaseTool):
    """请假申请"""

    name = "request_leave"
    description = (
        "请假申请。"
        "当用户说'请假'、'申请休假'时调用。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "leave_type": {
                "type": "string",
                "description": "请假类型（如: annual, sick, personal, maternity等）",
            },
            "start_date": {
                "type": "string",
                "description": "开始日期 YYYY-MM-DD",
            },
            "end_date": {
                "type": "string",
                "description": "结束日期 YYYY-MM-DD",
            },
            "days": {
                "type": "number",
                "description": "请假天数（可选，系统可自动计算）",
            },
            "reason": {
                "type": "string",
                "description": "请假原因",
                "maxLength": 500,
            },
        },
        "required": ["leave_type", "start_date", "end_date"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        leave_type = args.get("leave_type", "").strip()
        start_date = args.get("start_date", "").strip()
        end_date = args.get("end_date", "").strip()

        if not leave_type or not start_date or not end_date:
            return "❌ 请假类型、开始日期和结束日期不能为空"

        # 查找当前用户对应的员工ID
        try:
            emp_resp = client.table("employees").select("id").eq("user_id", user_id).eq("tenant_id", org_id).limit(1).execute()
            if not emp_resp.data:
                return "❌ 未找到您的员工信息，请联系管理员。"
            employee_id = emp_resp.data[0]["id"]
        except Exception as e:
            logger.error(f"查询员工信息失败: {e}")
            return f"❌ 查询员工信息失败: {str(e)}"

        data = {
            "leave_type": leave_type,
            "start_date": start_date,
            "end_date": end_date,
        }
        if args.get("days"):
            data["days"] = args["days"]
        if args.get("reason"):
            data["reason"] = args["reason"]

        try:
            leave = await attendance_service.request_leave(
                org_id=org_id,
                employee_id=employee_id,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
                days=args.get("days", 1),
                reason=args.get("reason"),
                db=client,
            )

            type_labels = {
                "annual": "年假",
                "sick": "病假",
                "personal": "事假",
                "maternity": "产假",
            }
            ltype = type_labels.get(leave_type, leave_type)

            return (
                f"✅ 请假申请已提交！\n\n"
                f"- 请假类型: {ltype}\n"
                f"- 开始日期: {start_date}\n"
                f"- 结束日期: {end_date}\n"
                f"- 状态: 待审批\n"
                f"- ID: {leave['id']}\n\n"
                f"请假申请已提交，等待审批。"
            )

        except Exception as e:
            logger.error(f"请假申请失败: {e}")
            return f"❌ 请假申请失败: {str(e)}"
