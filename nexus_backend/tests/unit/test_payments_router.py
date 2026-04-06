import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request, HTTPException
from app.routers.payments import create_order, get_order, list_orders

@pytest.fixture
def mock_request():
    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.state.db = MagicMock()
    req.state.org_id = "test-org-123"
    # Mocking req.json()
    req.json = AsyncMock(return_value={
        "plan_id": "pro",
        "payment_method": "alipay",
        "amount": 100.0
    })
    return req

@pytest.mark.asyncio
async def test_create_order_success(mock_request):
    """测试创建订单成功路径"""
    with patch("app.routers.payments.payment_service") as mock_service:
        mock_service.create_order = AsyncMock(return_value={"id": "order-123", "status": "pending"})

        response = await create_order(mock_request, user_id="user-123")
        # api_success returns {"success": True, "data": ...}
        assert response["success"] is True
        assert response["data"]["order"]["id"] == "order-123"

@pytest.mark.asyncio
async def test_create_order_missing_fields(mock_request):
    """测试缺失字段时的验证"""
    mock_request.json = AsyncMock(return_value={"amount": 100.0}) # Missing plan_id

    # api_error() returns HTTPException, not APIError
    with pytest.raises(HTTPException) as exc_info:
        await create_order(mock_request, user_id="user-123")
    assert exc_info.value.status_code == 400

@pytest.mark.asyncio
async def test_list_orders_success(mock_request):
    """测试获取订单列表"""
    with patch("app.routers.payments.payment_service") as mock_service:
        mock_service.list_orders = AsyncMock(return_value={
            "orders": [{"id": "o1"}],
            "total": 1,
            "page": 1,
            "page_size": 20
        })

        response = await list_orders(mock_request, user_id="user-123")
        # api_list returns {"success": True, "data": [...], "meta": {...}}
        assert response["success"] is True
        assert len(response["data"]) == 1

@pytest.mark.asyncio
async def test_get_order_not_found(mock_request):
    """测试订单未找到"""
    with patch("app.routers.payments.payment_service") as mock_service:
        mock_service.get_order_status = AsyncMock(return_value={"error": "Not found"})

        # api_error() returns HTTPException, not APIError
        with pytest.raises(HTTPException) as exc_info:
            await get_order("o-none", mock_request, user_id="user-123")
        assert exc_info.value.status_code == 404
