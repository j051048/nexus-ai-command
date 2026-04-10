"""
考勤管理工具集
提供打卡、排班、考勤统计、请假等功能
"""

import logging
from typing import Any

from app.services.attendance_service import attendance_service
from app.tools._shared import safe_tool_error

from ._shared import _get_client, _validate_uuid
from .base_tool import BaseTool

logger = logging.getLogger(__name__)


def _get_org_id(config: dict = None) -> str | None:
    return config.get("org_id") if config else None


# ============================================================================
# 考勤管理工具
# ============================================================================


class ClockInOutTool(BaseTool):
    """打卡（上班/下班/外勤打卡）"""

    name = "clock_in_out"
    description = "执行上班、下班或外勤打卡操作"
    examples = [
        {"input": {"clock_type": "clock_in"}, "output_summary": "执行上班打卡"},
        {"input": {"clock_type": "clock_out"}, "output_summary": "执行下班打卡"},
        {
            "input": {
                "clock_type": "field_work",
                "location": {"lat": 39.9, "lng": 116.4},
            },
            "output_summary": "执行外勤打卡并记录位置",
        },
    ]
    related_tools = ["get_attendance_record", "attendance_statistics"]
    gotchas = "打卡类型必填，可选值：clock_in/clock_out/field_work。系统会自动通过user_id查找员工信息，无需手动传employee_id。"

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
    domain = "attendance"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return self.format_result(data=None, summary="无法获取组织信息，请确保已正确登录")

        clock_type = args.get("clock_type", "").strip()
        if not clock_type:
            return self.format_result(data=None, summary="请指定打卡类型（clock_in/clock_out/field_work）")

        # 直接使用 user_id 作为 employee_id（users 表的 id 即用户ID）
        employee_id = user_id

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
            time_str = str(record.get('clock_time', ''))[:19]

            return self.format_result(
                data={"type": ctype, "clock_time": time_str, "id": record["id"]},
                summary=f"{ctype}成功",
                actions=[{"label": "查看考勤记录", "tool": "get_attendance_record"}],
            )

        except Exception as e:
            logger.error(f"打卡失败: {e}")
            return self.format_result(data=None, summary=safe_tool_error(e, "打卡"))


class GetAttendanceRecordTool(BaseTool):
    """查询考勤记录"""

    name = "get_attendance_record"
    description = "查询考勤打卡记录，支持按员工和日期范围筛选"
    examples = [
        {"input": {}, "output_summary": "返回当前用户的全部考勤记录"},
        {
            "input": {"start_date": "2026-03-01", "end_date": "2026-03-31"},
            "output_summary": "返回指定月份的考勤记录",
        },
        {
            "input": {"employee_id": "uuid-xxxx"},
            "output_summary": "返回指定员工的考勤记录",
        },
    ]
    related_tools = ["clock_in_out", "attendance_statistics", "list_shift_schedules"]
    gotchas = "不传employee_id则查当前用户自己的记录。日期格式为YYYY-MM-DD。"

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
    domain = "attendance"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return self.format_result(data=None, summary="无法获取组织信息，请确保已正确登录")

        if args.get("employee_id") and (
            err := _validate_uuid(args["employee_id"], "employee_id")
        ):
            return self.format_result(data=None, summary=f"参数错误: {err}")

        try:
            records = await attendance_service.get_attendance_records(
                org_id=org_id,
                employee_id=args.get("employee_id"),
                start_date=args.get("start_date"),
                end_date=args.get("end_date"),
                db=client,
            )

            if not records:
                return self.format_result(
                    data=[],
                    summary="当前暂无考勤记录",
                    actions=[{"label": "去打卡", "tool": "clock_in_out"}],
                )

            type_labels = {
                "clock_in": "上班",
                "clock_out": "下班",
                "field_work": "外勤",
            }

            items = []
            for r in records:
                ctype = type_labels.get(
                    r.get("clock_type", ""), r.get("clock_type", "")
                )
                items.append({
                    "clock_time": str(r.get('clock_time', ''))[:16],
                    "type": ctype,
                    "status": r.get('status', '正常'),
                })

            return self.format_result(
                data={"records": items, "total": len(records)},
                summary=f"共找到{len(records)}条考勤记录",
                actions=[{"label": "查看统计", "tool": "attendance_statistics"}],
            )

        except Exception as e:
            logger.error(f"查询考勤记录失败: {e}")
            return self.format_result(data=None, summary=safe_tool_error(e, "查询考勤记录"))


class CreateShiftScheduleTool(BaseTool):
    """创建排班计划"""

    name = "create_shift_schedule"
    description = "为指定员工创建排班计划，需管理员权限"
    examples = [
        {
            "input": {
                "employee_id": "uuid-xxxx",
                "shift_date": "2026-03-25",
                "shift_type_id": "uuid-yyyy",
            },
            "output_summary": "为指定员工在指定日期创建排班",
        },
    ]
    related_tools = ["list_shift_schedules", "get_attendance_record"]
    gotchas = (
        "三个参数均为必填。employee_id和shift_type_id必须是有效UUID。需要admin权限。"
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
    domain = "attendance"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return self.format_result(data=None, summary="无法获取组织信息，请确保已正确登录")

        employee_id = args.get("employee_id", "").strip()
        shift_date = args.get("shift_date", "").strip()
        shift_type_id = args.get("shift_type_id", "").strip()

        if not employee_id or not shift_date or not shift_type_id:
            return self.format_result(data=None, summary="员工ID、排班日期和班次类型不能为空")

        if err := _validate_uuid(employee_id, "employee_id"):
            return self.format_result(data=None, summary=f"参数错误: {err}")
        if err := _validate_uuid(shift_type_id, "shift_type_id"):
            return self.format_result(data=None, summary=f"参数错误: {err}")

        try:
            schedule = await attendance_service.create_shift_schedule(
                org_id=org_id,
                employee_id=employee_id,
                shift_date=shift_date,
                shift_type_id=shift_type_id,
                db=client,
            )

            return self.format_result(
                data={"employee_id": employee_id, "shift_date": shift_date, "id": schedule["id"]},
                summary="排班创建成功",
                actions=[{"label": "查看排班表", "tool": "list_shift_schedules"}],
            )

        except Exception as e:
            logger.error(f"创建排班失败: {e}")
            return self.format_result(data=None, summary=safe_tool_error(e, "创建排班"))


class ListShiftSchedulesTool(BaseTool):
    """查询排班表"""

    name = "list_shift_schedules"
    description = "查询排班表，支持按部门和日期范围筛选"
    examples = [
        {"input": {}, "output_summary": "返回全部排班记录"},
        {
            "input": {
                "department_id": "uuid-xxxx",
                "start_date": "2026-03-01",
                "end_date": "2026-03-31",
            },
            "output_summary": "返回指定部门本月的排班表",
        },
    ]
    related_tools = ["create_shift_schedule", "get_attendance_record"]
    gotchas = "不传筛选条件则返回全部排班。日期格式为YYYY-MM-DD。"

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
    domain = "attendance"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return self.format_result(data=None, summary="无法获取组织信息，请确保已正确登录")

        if args.get("department_id") and (
            err := _validate_uuid(args["department_id"], "department_id")
        ):
            return self.format_result(data=None, summary=f"参数错误: {err}")

        try:
            schedules = await attendance_service.list_shift_schedules(
                org_id=org_id,
                department_id=args.get("department_id"),
                start_date=args.get("start_date"),
                end_date=args.get("end_date"),
                db=client,
            )

            if not schedules:
                return self.format_result(
                    data=[],
                    summary="当前暂无排班记录",
                    actions=[{"label": "创建排班", "tool": "create_shift_schedule"}],
                )

            items = []
            for s in schedules:
                employee_name = (
                    s.get("employee", {}).get("name", "未知")
                    if s.get("employee")
                    else "未知"
                )
                shift_name = s.get('shift_type', {}).get('name', '未知') if s.get('shift_type') else '未知'
                items.append({
                    "shift_date": s.get("shift_date"),
                    "employee_name": employee_name,
                    "shift_type": shift_name,
                })

            return self.format_result(
                data={"schedules": items, "total": len(schedules)},
                summary=f"共找到{len(schedules)}条排班记录",
                actions=[{"label": "创建排班", "tool": "create_shift_schedule"}],
            )

        except Exception as e:
            logger.error(f"查询排班表失败: {e}")
            return self.format_result(data=None, summary=safe_tool_error(e, "查询排班表"))


class AttendanceStatisticsTool(BaseTool):
    """考勤统计"""

    name = "attendance_statistics"
    description = "获取考勤统计数据，包括准时率、迟到和早退次数"
    examples = [
        {"input": {}, "output_summary": "返回全组织的考勤统计"},
        {
            "input": {
                "department_id": "uuid-xxxx",
                "start_date": "2026-03-01",
                "end_date": "2026-03-31",
            },
            "output_summary": "返回指定部门本月的考勤统计",
        },
    ]
    related_tools = ["get_attendance_record", "list_shift_schedules"]
    gotchas = "不传筛选条件则统计全组织全时段数据。返回的on_time_rate为百分比数值。"

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
    domain = "attendance"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return self.format_result(data=None, summary="无法获取组织信息，请确保已正确登录")

        if args.get("department_id") and (
            err := _validate_uuid(args["department_id"], "department_id")
        ):
            return self.format_result(data=None, summary=f"参数错误: {err}")

        try:
            stats = await attendance_service.get_attendance_statistics(
                org_id=org_id,
                department_id=args.get("department_id"),
                start_date=args.get("start_date"),
                end_date=args.get("end_date"),
                db=client,
            )

            return self.format_result(
                data={
                    "total_records": stats.get("total_records", 0),
                    "on_time_count": stats.get("on_time_count", 0),
                    "late_count": stats.get("late_count", 0),
                    "early_leave_count": stats.get("early_leave_count", 0),
                    "on_time_rate": stats.get("on_time_rate", 0),
                },
                summary=f"考勤统计: 准时率{stats.get('on_time_rate', 0)}%",
                actions=[{"label": "查看考勤记录", "tool": "get_attendance_record"}],
            )

        except Exception as e:
            logger.error(f"获取考勤统计失败: {e}")
            return self.format_result(data=None, summary=safe_tool_error(e, "获取考勤统计"))


class RequestLeaveTool(BaseTool):
    """请假申请"""

    name = "request_leave"
    description = "提交请假申请，支持年假、病假、事假、产假等类型，与排班系统联动"
    examples = [
        {
            "input": {
                "leave_type": "annual",
                "start_date": "2026-04-01",
                "end_date": "2026-04-03",
                "reason": "家庭旅行",
            },
            "output_summary": "提交3天年假申请",
        },
        {
            "input": {
                "leave_type": "sick",
                "start_date": "2026-03-20",
                "end_date": "2026-03-20",
                "days": 1,
            },
            "output_summary": "提交1天病假申请",
        },
    ]
    related_tools = ["get_attendance_record", "list_shift_schedules"]
    gotchas = "leave_type可选值：annual/sick/personal/maternity。start_date和end_date均为必填。提交后状态为待审批。与create_leave_request功能相同，系统会自动选择其一。"

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
    domain = "attendance"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return self.format_result(data=None, summary="无法获取组织信息，请确保已正确登录")

        leave_type = args.get("leave_type", "").strip()
        start_date = args.get("start_date", "").strip()
        end_date = args.get("end_date", "").strip()

        if not leave_type or not start_date or not end_date:
            return self.format_result(data=None, summary="请假类型、开始日期和结束日期不能为空")

        # 直接使用 user_id 作为 employee_id（users 表的 id 即用户ID）
        employee_id = user_id

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

            return self.format_result(
                data={
                    "leave_type": ltype,
                    "start_date": start_date,
                    "end_date": end_date,
                    "status": "待审批",
                    "id": leave["id"],
                },
                summary=f"{ltype}申请已提交，等待审批",
                actions=[{"label": "查看考勤记录", "tool": "get_attendance_record"}],
            )

        except Exception as e:
            logger.error(f"请假申请失败: {e}")
            return self.format_result(data=None, summary=safe_tool_error(e, "请假申请"))
