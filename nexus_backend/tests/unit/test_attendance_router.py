from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.table = MagicMock()
    return db

@pytest.fixture
def mock_request(mock_db):
    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.state.db = mock_db
    req.state.org_id = "test-org-123"
    return req

@pytest.mark.asyncio
async def test_clock_in_success(mock_request):
    from app.routers.attendance import ClockBody, clock_in_out
    body = ClockBody(clock_type="in", employee_id="emp-1", location="Office")

    with patch("app.routers.attendance.attendance_service.clock_in_out", new_callable=AsyncMock) as mock_action:
        mock_action.return_value = {"id": "c1", "status": "success"}

        response = await clock_in_out(body=body, req=mock_request, user_id="u1")

        assert response["success"] is True
        assert response["message"] == "打卡成功"
        mock_action.assert_called_once()

@pytest.mark.asyncio
async def test_get_attendance_records_success(mock_request):
    from app.routers.attendance import get_attendance_records

    with patch("app.routers.attendance.attendance_service.get_attendance_records", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = [{"id": "r1", "clock_in": "2026-01-01T09:00:00"}]

        response = await get_attendance_records(req=mock_request, employee_id="emp-1")

        assert response["success"] is True
        assert len(response["data"]["records"]) == 1

@pytest.mark.asyncio
async def test_create_shift_success(mock_request):
    from app.routers.attendance import ShiftScheduleCreate, create_shift_schedule
    body = ShiftScheduleCreate(employee_id="emp-1", shift_date="2026-01-01", shift_type_id="st-1")

    with patch("app.routers.attendance.attendance_service.create_shift_schedule", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = {"id": "s1"}

        response = await create_shift_schedule(body=body, req=mock_request, user_id="admin-1")

        assert response["success"] is True
        assert response["data"]["shift"]["id"] == "s1"

@pytest.mark.asyncio
async def test_request_leave_success(mock_request):
    from app.routers.attendance import LeaveRequestBody, request_leave
    body = LeaveRequestBody(employee_id="emp-1", leave_type="sick", start_date="2026-01-01", end_date="2026-01-02", days=2)

    with patch("app.routers.attendance.attendance_service.request_leave", new_callable=AsyncMock) as mock_leave:
        mock_leave.return_value = {"id": "l1", "status": "pending"}

        response = await request_leave(body=body, req=mock_request, user_id="u1")

        assert response["success"] is True
        assert response["data"]["leave"]["id"] == "l1"

@pytest.mark.asyncio
async def test_attendance_statistics_success(mock_request):
    from app.routers.attendance import attendance_statistics

    with patch("app.routers.attendance.attendance_service.get_attendance_statistics", new_callable=AsyncMock) as mock_stats:
        mock_stats.return_value = {"total_days": 20, "present": 18, "absent": 2}

        response = await attendance_statistics(req=mock_request)

        assert response["success"] is True
        assert response["data"]["present"] == 18
