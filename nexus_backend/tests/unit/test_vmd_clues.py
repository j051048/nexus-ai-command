import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import Request, HTTPException
from app.routers.vmd_clues import list_vmd_clues, get_vmd_clue_detail

PATCH_ADMIN_DB = "app.routers.vmd_clues._get_admin_db"

@pytest.mark.asyncio
class TestVMDCluesUnit:
    """VMD 线索路由单元测试"""

    async def test_list_vmd_clues_success(self):
        """测试获取商机线索列表成功路径"""
        mock_data = [
            {"id": 1, "title": "Clue 1"},
            {"id": 2, "title": "Clue 2"}
        ]

        mock_res = MagicMock()
        mock_res.data = mock_data

        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.execute = AsyncMock(return_value=mock_res)

        mock_db = MagicMock()
        mock_db.table.return_value = mock_query

        mock_req = MagicMock(spec=Request)
        mock_req.state.org_id = "org-123"

        with patch(PATCH_ADMIN_DB, return_value=mock_db):
            response = await list_vmd_clues(mock_req, user_id="user-123")

        assert response["success"] is True
        assert len(response["data"]["clues"]) == 2

    async def test_list_vmd_clues_with_filters(self):
        """测试带过滤条件的商机线索列表"""
        mock_res = MagicMock()
        mock_res.data = [{"id": 1, "status": "new", "priority": "high"}]

        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.execute = AsyncMock(return_value=mock_res)

        mock_db = MagicMock()
        mock_db.table.return_value = mock_query

        mock_req = MagicMock(spec=Request)
        mock_req.state.org_id = "org-123"

        with patch(PATCH_ADMIN_DB, return_value=mock_db):
            response = await list_vmd_clues(mock_req, status="new", priority="high", user_id="user-123")

        assert response["success"] is True
        assert len(response["data"]["clues"]) == 1
        mock_query.eq.assert_any_call("status", "new")
        mock_query.eq.assert_any_call("priority", "high")

    async def test_get_vmd_clue_detail_success(self):
        """测试获取线索详情成功"""
        mock_res = MagicMock()
        mock_res.data = {"id": "clue-123", "title": "Lead Details", "clue_code": "CL-001"}

        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.maybe_single.return_value = mock_query
        mock_query.execute = AsyncMock(return_value=mock_res)

        mock_db = MagicMock()
        mock_db.table.return_value = mock_query

        mock_req = MagicMock(spec=Request)
        mock_req.state.org_id = "org-123"

        with patch(PATCH_ADMIN_DB, return_value=mock_db):
            response = await get_vmd_clue_detail(mock_req, clue_id="CL-001", user_id="user-123")

        assert response["success"] is True
        assert response["data"]["clue_code"] == "CL-001"

    async def test_get_vmd_clue_detail_not_found(self):
        """测试线索不存在路径"""
        mock_res = MagicMock()
        mock_res.data = None

        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.maybe_single.return_value = mock_query
        mock_query.execute = AsyncMock(return_value=mock_res)

        mock_db = MagicMock()
        mock_db.table.return_value = mock_query

        mock_req = MagicMock(spec=Request)
        mock_req.state.org_id = "org-123"

        with patch(PATCH_ADMIN_DB, return_value=mock_db):
            with pytest.raises(HTTPException) as excinfo:
                await get_vmd_clue_detail(mock_req, clue_id="999", user_id="user-123")

        assert excinfo.value.status_code == 404
        assert "不存在" in excinfo.value.detail["message"]
