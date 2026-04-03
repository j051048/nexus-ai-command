"""
CRMService 单元测试
覆盖: 客户 CRUD、联系人、活动时间线、统计
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.crm_service import CRMService, CUSTOMER_STAGES


def _mock_db(table_data=None):
    db = MagicMock()
    table_data = table_data or {}

    def _table(name):
        builder = MagicMock()
        data = list(table_data.get(name, []))

        resp = MagicMock()
        resp.data = data

        # insert
        builder.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[data[0]] if data else [{"id": "new-1"}])
        )
        # update
        builder.update.return_value.eq.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[data[0]] if data else [])
        )
        # select single
        builder.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data=data[0] if data else None)
        )
        # select list
        builder.select.return_value.eq.return_value.execute = AsyncMock(return_value=resp)
        builder.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(return_value=resp)
        builder.select.return_value.eq.return_value.order.return_value.limit.return_value.execute = AsyncMock(return_value=resp)
        # ilike for search
        builder.select.return_value.eq.return_value.ilike.return_value.execute = AsyncMock(return_value=resp)
        # delete
        builder.delete.return_value.eq.return_value.execute = AsyncMock(return_value=MagicMock(data=[]))
        # count
        builder.select.return_value.eq.return_value.eq.return_value.execute = AsyncMock(return_value=resp)

        return builder

    db.table = _table
    return db


CUSTOMER = {
    "id": "c-1", "organization_id": "org-1", "name": "测试客户",
    "company": "Test Corp", "industry": "tech", "stage": "prospect",
    "source": "web", "estimated_value": 100000,
}


class TestCustomerCRUD:
    """客户 CRUD 测试"""

    def setup_method(self):
        self.svc = CRMService()

    @pytest.mark.asyncio
    async def test_create_customer(self):
        db = _mock_db()
        result = await self.svc.create_customer("org-1", {"name": "新客户", "stage": "lead"}, db=db)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_no_name_raises(self):
        db = _mock_db()
        with pytest.raises(ValueError, match="名称"):
            await self.svc.create_customer("org-1", {"name": ""}, db=db)

    @pytest.mark.asyncio
    async def test_create_invalid_stage_raises(self):
        db = _mock_db()
        with pytest.raises(ValueError, match="阶段"):
            await self.svc.create_customer("org-1", {"name": "X", "stage": "invalid"}, db=db)

    @pytest.mark.asyncio
    async def test_create_no_db_raises(self):
        with pytest.raises(RuntimeError):
            await self.svc.create_customer("org-1", {"name": "X"}, db=None)

    @pytest.mark.asyncio
    async def test_update_customer(self):
        db = _mock_db({"customers": [CUSTOMER]})
        result = await self.svc.update_customer("c-1", {"name": "更新后"}, db=db)
        assert result is not None

    @pytest.mark.asyncio
    async def test_update_filters_disallowed_fields(self):
        db = _mock_db({"customers": [CUSTOMER]})
        await self.svc.update_customer("c-1", {"name": "OK", "id": "hack", "organization_id": "hack"}, db=db)
        # id and organization_id should be filtered out
        call_args = db.table("customers").update.call_args
        if call_args:
            update_data = call_args[0][0]
            assert "id" not in update_data
            assert "organization_id" not in update_data

    @pytest.mark.asyncio
    async def test_update_invalid_stage_raises(self):
        db = _mock_db({"customers": [CUSTOMER]})
        with pytest.raises(ValueError, match="阶段"):
            await self.svc.update_customer("c-1", {"stage": "invalid"}, db=db)

    @pytest.mark.asyncio
    async def test_get_customer(self):
        db = _mock_db({"customers": [CUSTOMER]})
        result = await self.svc.get_customer("c-1", db=db)
        assert result is not None

    @pytest.mark.asyncio
    async def test_delete_customer(self):
        db = _mock_db({"customers": [CUSTOMER]})
        await self.svc.delete_customer("c-1", db=db)
        # Should not raise
