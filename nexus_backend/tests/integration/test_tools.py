"""工具单元测试"""
import pytest
from app.tools.crm_tools import get_customer, create_customer

@pytest.mark.asyncio
async def test_get_customer(test_user):
    result = await get_customer("cust-001", test_user["tenant_id"])
    assert result is not None

@pytest.mark.asyncio
async def test_create_customer(test_user):
    data = {"name": "测试客户", "email": "test@example.com"}
    result = await create_customer(data, test_user["tenant_id"])
    assert "customer_id" in result
