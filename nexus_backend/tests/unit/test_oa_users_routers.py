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

@pytest.mark.asyncio
async def test_get_oa_stats_success(mock_request):
    """测试获取OA统计数据"""
    # Mock database responses for three count queries
    mock_response = MagicMock()
    mock_response.count = 5
    mock_request.state.db.table().select().eq().execute = AsyncMock(return_value=mock_response)
    mock_request.state.db.table().select().not_.eq().execute = AsyncMock(return_value=mock_response)

    response = await get_oa_stats(mock_request, user_id="user-123")
    assert response["status"] == "success"
    assert "metrics" in response["data"]
    assert response["data"]["metrics"]["today_attendance"] == 5

@pytest.mark.asyncio
async def test_get_today_attendance_empty(mock_request):
    """测试获取打卡记录为空时的场景"""
    mock_response = MagicMock()
    mock_response.data = []
    mock_request.state.db.table().select().eq().eq().execute = AsyncMock(return_value=mock_response)

    response = await get_today_attendance(mock_request, user_id="user-123")
    assert response["status"] == "success"
    assert response["data"]["records"] == []

@pytest.mark.asyncio
async def test_get_org_members_success(mock_request):
    """测试获取组织成员"""
    mock_response = MagicMock()
    mock_response.data = [{"id": "u1", "full_name": "Test User"}]
    mock_request.state.db.table().select().eq().execute = AsyncMock(return_value=mock_response)

    response = await get_org_members(mock_request, user_id="user-123")
    assert response["status"] == "success"
    assert len(response["data"]["members"]) == 1
    assert response["data"]["members"][0]["full_name"] == "Test User"

@pytest.mark.asyncio
async def test_get_oa_stats_db_error(mock_request):
    """测试数据库报错时的兼容性"""
    mock_request.state.db.table().select().eq().execute = AsyncMock(side_effect=Exception("DB Error"))
    
    response = await get_oa_stats(mock_request, user_id="user-123")
    # Even on error, should return 0 metrics as per implementation
    assert response["status"] == "success"
    assert response["data"]["metrics"]["today_attendance"] == 0
