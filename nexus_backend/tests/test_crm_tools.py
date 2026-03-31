"""
Test suite for CRM tools.
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.tools.crm_tools import get_customer, create_customer, update_customer


@pytest.mark.asyncio
async def test_get_customer_success():
    """测试获取客户成功"""
    with patch('app.tools.crm_tools.supabase') as mock_supabase:
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "id": "123",
            "name": "测试客户",
            "phone": "13800138000"
        }

        result = await get_customer(customer_id="123", org_id="test_org")

        assert result["id"] == "123"
        assert result["name"] == "测试客户"


@pytest.mark.asyncio
async def test_get_customer_not_found():
    """测试客户不存在"""
    with patch('app.tools.crm_tools.supabase') as mock_supabase:
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.side_effect = Exception("Not found")

        with pytest.raises(Exception):
            await get_customer(customer_id="999", org_id="test_org")


@pytest.mark.asyncio
async def test_create_customer():
    """测试创建客户"""
    with patch('app.tools.crm_tools.supabase') as mock_supabase:
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [{
            "id": "new_123",
            "name": "新客户"
        }]

        result = await create_customer(
            name="新客户",
            phone="13900139000",
            org_id="test_org"
        )

        assert result["id"] == "new_123"
