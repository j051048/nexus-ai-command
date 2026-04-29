"""
考勤管理工具 (attendance_tools.py) 单元测试
覆盖：打卡、考勤记录、排班管理、考勤统计、请假申请
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

FAKE_USER_ID = "user-" + "a" * 32
FAKE_ORG_ID = "org-" + "b" * 32
CONFIG = {"org_id": FAKE_ORG_ID, "token": "jwt-test"}


def _mock_client():
    return MagicMock()


def _load_tool(name: str):
    from app.tools import get_tool
    tool = get_tool(name)
    assert tool is not None, f"Tool '{name}' not found in registry"
    return tool


# ════════════════════════════════════════════════════════════════════
# 打卡工具
# ════════════════════════════════════════════════════════════════════


class TestClockInOutTool:
    """打卡工具测试"""

    @pytest.mark.asyncio
    async def test_clock_in_success(self):
        tool = _load_tool("clock_in_out")
        record = {"id": str(uuid.uuid4()), "clock_time": "2026-04-29T09:00:00"}
        with (
            patch("app.tools.attendance_tools._get_client", return_value=_mock_client()),
            patch("app.tools.attendance_tools.attendance_service") as svc,
        ):
            svc.clock_in_out = AsyncMock(return_value=record)
            result = await tool.run({"clock_type": "clock_in"}, FAKE_USER_ID, CONFIG)
        assert "上班打卡" in str(result) or "成功" in str(result) or "✅" in str(result)

    @pytest.mark.asyncio
    async def test_clock_out_success(self):
        tool = _load_tool("clock_in_out")
        record = {"id": str(uuid.uuid4()), "clock_time": "2026-04-29T18:00:00"}
        with (
            patch("app.tools.attendance_tools._get_client", return_value=_mock_client()),
            patch("app.tools.attendance_tools.attendance_service") as svc,
        ):
            svc.clock_in_out = AsyncMock(return_value=record)
            result = await tool.run({"clock_type": "clock_out"}, FAKE_USER_ID, CONFIG)
        assert "下班打卡" in str(result) or "成功" in str(result) or "✅" in str(result)

    @pytest.mark.asyncio
    async def test_field_work_with_location(self):
        tool = _load_tool("clock_in_out")
        record = {"id": str(uuid.uuid4()), "clock_time": "2026-04-29T14:00:00"}
        with (
            patch("app.tools.attendance_tools._get_client", return_value=_mock_client()),
            patch("app.tools.attendance_tools.attendance_service") as svc,
        ):
            svc.clock_in_out = AsyncMock(return_value=record)
            result = await tool.run(
                {"clock_type": "field_work", "location": {"lat": 39.9, "lng": 116.4}},
                FAKE_USER_ID, CONFIG,
            )
        assert "外勤打卡" in str(result) or "成功" in str(result) or "✅" in str(result)

    @pytest.mark.asyncio
    async def test_clock_empty_type(self):
        tool = _load_tool("clock_in_out")
        with patch("app.tools.attendance_tools._get_client", return_value=_mock_client()):
            result = await tool.run({"clock_type": ""}, FAKE_USER_ID, CONFIG)
        assert "打卡类型" in str(result) or "clock_in" in str(result)

    @pytest.mark.asyncio
    async def test_clock_no_org(self):
        tool = _load_tool("clock_in_out")
        with patch("app.tools.attendance_tools._get_client", return_value=_mock_client()):
            result = await tool.run({"clock_type": "clock_in"}, FAKE_USER_ID, {})
        assert "无法获取组织" in str(result) or "登录" in str(result) or "❌" in str(result)

    @pytest.mark.asyncio
    async def test_clock_service_error(self):
        tool = _load_tool("clock_in_out")
        with (
            patch("app.tools.attendance_tools._get_client", return_value=_mock_client()),
            patch("app.tools.attendance_tools.attendance_service") as svc,
        ):
            svc.clock_in_out = AsyncMock(side_effect=Exception("Network error"))
            result = await tool.run({"clock_type": "clock_in"}, FAKE_USER_ID, CONFIG)
        assert "失败" in str(result) or "error" in str(result).lower() or "❌" in str(result)


# ════════════════════════════════════════════════════════════════════
# 考勤记录查询
# ════════════════════════════════════════════════════════════════════


class TestGetAttendanceRecordTool:
    """考勤记录查询"""

    @pytest.mark.asyncio
    async def test_get_records_success(self):
        tool = _load_tool("get_attendance_record")
        records = [
            {"clock_time": "2026-04-29T09:00:00", "clock_type": "clock_in", "status": "normal"},
            {"clock_time": "2026-04-29T18:05:00", "clock_type": "clock_out", "status": "normal"},
        ]
        with (
            patch("app.tools.attendance_tools._get_client", return_value=_mock_client()),
            patch("app.tools.attendance_tools.attendance_service") as svc,
        ):
            svc.get_attendance_records = AsyncMock(return_value=records)
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "2" in str(result) or "考勤" in str(result)

    @pytest.mark.asyncio
    async def test_get_records_empty(self):
        tool = _load_tool("get_attendance_record")
        with (
            patch("app.tools.attendance_tools._get_client", return_value=_mock_client()),
            patch("app.tools.attendance_tools.attendance_service") as svc,
        ):
            svc.get_attendance_records = AsyncMock(return_value=[])
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "暂无" in str(result) or "打卡" in str(result)

    @pytest.mark.asyncio
    async def test_get_records_with_date_range(self):
        tool = _load_tool("get_attendance_record")
        records = [
            {"clock_time": "2026-04-01T09:00:00", "clock_type": "clock_in", "status": "normal"},
        ]
        with (
            patch("app.tools.attendance_tools._get_client", return_value=_mock_client()),
            patch("app.tools.attendance_tools.attendance_service") as svc,
        ):
            svc.get_attendance_records = AsyncMock(return_value=records)
            result = await tool.run(
                {"start_date": "2026-04-01", "end_date": "2026-04-30"},
                FAKE_USER_ID, CONFIG,
            )
        assert "1" in str(result)


# ════════════════════════════════════════════════════════════════════
# 排班管理
# ════════════════════════════════════════════════════════════════════


class TestCreateShiftScheduleTool:
    """排班管理"""

    @pytest.mark.asyncio
    async def test_create_shift_success(self):
        tool = _load_tool("create_shift_schedule")
        emp_id = str(uuid.uuid4())
        shift_type_id = str(uuid.uuid4())
        schedule = {"id": str(uuid.uuid4())}
        with (
            patch("app.tools.attendance_tools._get_client", return_value=_mock_client()),
            patch("app.tools.attendance_tools.attendance_service") as svc,
        ):
            svc.create_shift_schedule = AsyncMock(return_value=schedule)
            result = await tool.run(
                {"employee_id": emp_id, "shift_date": "2026-05-01", "shift_type_id": shift_type_id},
                FAKE_USER_ID, CONFIG,
            )
        assert "成功" in str(result) or "排班" in str(result) or "✅" in str(result)

    @pytest.mark.asyncio
    async def test_create_shift_invalid_uuid(self):
        tool = _load_tool("create_shift_schedule")
        with patch("app.tools.attendance_tools._get_client", return_value=_mock_client()):
            result = await tool.run(
                {"employee_id": "bad", "shift_date": "2026-05-01", "shift_type_id": "bad"},
                FAKE_USER_ID, CONFIG,
            )
        assert "❌" in str(result) or "参数" in str(result) or "UUID" in str(result)


# ════════════════════════════════════════════════════════════════════
# 考勤统计
# ════════════════════════════════════════════════════════════════════


class TestAttendanceStatisticsTool:
    """考勤统计"""

    @pytest.mark.asyncio
    async def test_statistics_success(self):
        tool = _load_tool("attendance_statistics")
        stats = {
            "total_records": 200, "on_time_count": 185,
            "late_count": 10, "early_leave_count": 5, "on_time_rate": 92.5,
        }
        with (
            patch("app.tools.attendance_tools._get_client", return_value=_mock_client()),
            patch("app.tools.attendance_tools.attendance_service") as svc,
        ):
            svc.get_attendance_statistics = AsyncMock(return_value=stats)
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        result_str = str(result)
        assert "92" in result_str or "准时" in result_str or "统计" in result_str

    @pytest.mark.asyncio
    async def test_statistics_with_department(self):
        tool = _load_tool("attendance_statistics")
        dept_id = str(uuid.uuid4())
        stats = {
            "total_records": 50, "on_time_count": 48,
            "late_count": 2, "early_leave_count": 0, "on_time_rate": 96,
        }
        with (
            patch("app.tools.attendance_tools._get_client", return_value=_mock_client()),
            patch("app.tools.attendance_tools.attendance_service") as svc,
        ):
            svc.get_attendance_statistics = AsyncMock(return_value=stats)
            result = await tool.run({"department_id": dept_id}, FAKE_USER_ID, CONFIG)
        assert "96" in str(result) or "统计" in str(result)


# ════════════════════════════════════════════════════════════════════
# 请假申请
# ════════════════════════════════════════════════════════════════════


class TestRequestLeaveTool:
    """请假申请"""

    @pytest.mark.asyncio
    async def test_request_leave_success(self):
        tool = _load_tool("request_leave")
        leave = {"id": str(uuid.uuid4()), "status": "pending"}
        with (
            patch("app.tools.attendance_tools._get_client", return_value=_mock_client()),
            patch("app.tools.attendance_tools.attendance_service") as svc,
        ):
            svc.request_leave = AsyncMock(return_value=leave)
            result = await tool.run(
                {"leave_type": "annual", "start_date": "2026-05-01",
                 "end_date": "2026-05-03", "reason": "旅行"},
                FAKE_USER_ID, CONFIG,
            )
        assert "年假" in str(result) or "审批" in str(result) or "✅" in str(result)

    @pytest.mark.asyncio
    async def test_request_leave_missing_fields(self):
        tool = _load_tool("request_leave")
        with patch("app.tools.attendance_tools._get_client", return_value=_mock_client()):
            result = await tool.run(
                {"leave_type": "", "start_date": "", "end_date": ""},
                FAKE_USER_ID, CONFIG,
            )
        assert "不能为空" in str(result) or "❌" in str(result) or "请指定" in str(result)

    @pytest.mark.asyncio
    async def test_request_sick_leave(self):
        tool = _load_tool("request_leave")
        leave = {"id": str(uuid.uuid4()), "status": "pending"}
        with (
            patch("app.tools.attendance_tools._get_client", return_value=_mock_client()),
            patch("app.tools.attendance_tools.attendance_service") as svc,
        ):
            svc.request_leave = AsyncMock(return_value=leave)
            result = await tool.run(
                {"leave_type": "sick", "start_date": "2026-05-01",
                 "end_date": "2026-05-01", "days": 1},
                FAKE_USER_ID, CONFIG,
            )
        assert "病假" in str(result) or "审批" in str(result) or "✅" in str(result)

    @pytest.mark.asyncio
    async def test_request_leave_service_error(self):
        tool = _load_tool("request_leave")
        with (
            patch("app.tools.attendance_tools._get_client", return_value=_mock_client()),
            patch("app.tools.attendance_tools.attendance_service") as svc,
        ):
            svc.request_leave = AsyncMock(side_effect=Exception("DB down"))
            result = await tool.run(
                {"leave_type": "annual", "start_date": "2026-05-01",
                 "end_date": "2026-05-02"},
                FAKE_USER_ID, CONFIG,
            )
        assert "失败" in str(result) or "error" in str(result).lower() or "❌" in str(result)

class TestListShiftSchedulesTool:
    """查询排班记录"""

    @pytest.mark.asyncio
    async def test_list_shift_schedules_success(self):
        tool = _load_tool("list_shift_schedules")
        schedules = [
            {"shift_date": "2026-05-01", "employee": {"name": "张三"}, "shift_type": {"name": "早班"}}
        ]
        with (
            patch("app.tools.attendance_tools._get_client", return_value=_mock_client()),
            patch("app.tools.attendance_tools.attendance_service") as svc,
        ):
            svc.list_shift_schedules = AsyncMock(return_value=schedules)
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "张三" in str(result) or "早班" in str(result)

    @pytest.mark.asyncio
    async def test_list_shift_schedules_empty(self):
        tool = _load_tool("list_shift_schedules")
        with (
            patch("app.tools.attendance_tools._get_client", return_value=_mock_client()),
            patch("app.tools.attendance_tools.attendance_service") as svc,
        ):
            svc.list_shift_schedules = AsyncMock(return_value=[])
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "暂无" in str(result) or "0条" in str(result)

    @pytest.mark.asyncio
    async def test_list_shift_schedules_invalid_uuid(self):
        tool = _load_tool("list_shift_schedules")
        with patch("app.tools.attendance_tools._get_client", return_value=_mock_client()):
            result = await tool.run({"department_id": "invalid"}, FAKE_USER_ID, CONFIG)
        assert "❌" in str(result) or "参数错误" in str(result)

    @pytest.mark.asyncio
    async def test_list_shift_schedules_no_org(self):
        tool = _load_tool("list_shift_schedules")
        with patch("app.tools.attendance_tools._get_client", return_value=_mock_client()):
            result = await tool.run({}, FAKE_USER_ID, {})
        assert "无法获取" in str(result) or "组织" in str(result)

    @pytest.mark.asyncio
    async def test_list_shift_schedules_error(self):
        tool = _load_tool("list_shift_schedules")
        with (
            patch("app.tools.attendance_tools._get_client", return_value=_mock_client()),
            patch("app.tools.attendance_tools.attendance_service") as svc,
        ):
            svc.list_shift_schedules = AsyncMock(side_effect=Exception("DB Error"))
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "失败" in str(result) or "error" in str(result).lower()
