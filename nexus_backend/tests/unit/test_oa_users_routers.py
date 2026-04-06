import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request
from app.routers.oa import get_oa_stats, get_today_attendance
from app.routers.users import get_org_members

@pytest.fixture
def mock_request():
    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.state.db = MagicMock()
    req.state.org_id = "test-org-123"
    return req

def _make_count_response(count_val):
    """Helper to create a mock response with .count attribute for count='exact' queries."""
    resp = MagicMock()
    resp.count = count_val
    return resp

@pytest.mark.asyncio
async def test_get_oa_stats_success(mock_request):
    """测试获取OA统计数据"""
    # get_oa_stats chains: db.table(...).select("id", count="exact").eq(...).execute()
    # and db.table(...).select("id", count="exact").neq(...).execute()
    # We need the final .execute() to return an object with .count

    attendance_resp = _make_count_response(5)
    leave_resp = _make_count_response(3)
    task_resp = _make_count_response(2)

    db = mock_request.state.db
    # Each db.table() call returns a new chain; use side_effect to sequence them
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.neq.return_value = chain
    chain.execute = AsyncMock(side_effect=[attendance_resp, leave_resp, task_resp])
    db.table.return_value = chain

    response = await get_oa_stats(mock_request, user_id="user-123")
    # api_success returns {"success": True, "data": ...}
    assert response["success"] is True
    assert "metrics" in response["data"]
    assert response["data"]["metrics"]["today_attendance"] == 5

@pytest.mark.asyncio
async def test_get_today_attendance_empty(mock_request):
    """测试获取打卡记录为空时的场景"""
    mock_response = MagicMock()
    mock_response.data = []

    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.execute = AsyncMock(return_value=mock_response)
    mock_request.state.db.table.return_value = chain

    response = await get_today_attendance(mock_request, user_id="user-123")
    # api_success returns {"success": True, "data": ...}
    assert response["success"] is True
    assert response["data"]["records"] == []

@pytest.mark.asyncio
async def test_get_org_members_success(mock_request):
    """测试获取组织成员"""
    mock_response = MagicMock()
    mock_response.data = [{"id": "u1", "full_name": "Test User"}]

    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.execute = AsyncMock(return_value=mock_response)
    mock_request.state.db.table.return_value = chain

    response = await get_org_members(mock_request, user_id="user-123")
    # api_success returns {"success": True, "data": ...}
    assert response["success"] is True
    assert len(response["data"]["members"]) == 1
    assert response["data"]["members"][0]["full_name"] == "Test User"

@pytest.mark.asyncio
async def test_get_oa_stats_db_error(mock_request):
    """测试数据库报错时的兼容性"""
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.neq.return_value = chain
    chain.execute = AsyncMock(side_effect=Exception("DB Error"))
    mock_request.state.db.table.return_value = chain

    response = await get_oa_stats(mock_request, user_id="user-123")
    # Even on error, the router catches Exception and returns fallback with 0 metrics
    assert response["success"] is True
    assert response["data"]["metrics"]["today_attendance"] == 0
