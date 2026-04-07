from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from app.routers.vmd_compliance import list_vmd_compliance_history, list_vmd_compliance_rules

PATCH_ADMIN_DB = "app.routers.vmd_compliance._get_admin_db"

@pytest.mark.asyncio
class TestVMDComplianceUnit:
    """VMD 合规路由单元测试"""

    async def test_list_vmd_compliance_history_success(self):
        """测试获取合规审计历史成功"""
        mock_data = [
            {"id": "r1", "report_name": "Report 1", "created_at": "2024-04-01"},
            {"id": "r2", "report_name": "Report 2", "created_at": "2024-04-02"}
        ]

        mock_res = MagicMock()
        mock_res.data = mock_data

        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.execute = AsyncMock(return_value=mock_res)

        mock_db = MagicMock()
        mock_db.table.return_value = mock_query

        mock_req = MagicMock(spec=Request)
        mock_req.state.org_id = "org-123"

        with patch(PATCH_ADMIN_DB, return_value=mock_db):
            response = await list_vmd_compliance_history(mock_req, user_id="user-123")

        assert response["success"] is True
        assert len(response["data"]) == 2
        mock_db.table.assert_called_with("vmd_reports")

    async def test_list_vmd_compliance_rules_success(self):
        """测试获取合规检查规则成功"""
        mock_res = MagicMock()
        mock_res.data = [{"id": "rule-1", "name": "Rule 1"}]

        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.execute = AsyncMock(return_value=mock_res)

        mock_db = MagicMock()
        mock_db.table.return_value = mock_query

        mock_req = MagicMock(spec=Request)
        mock_req.state.org_id = "org-123"

        with patch(PATCH_ADMIN_DB, return_value=mock_db):
            response = await list_vmd_compliance_rules(mock_req, user_id="user-123")

        assert response["success"] is True
        assert len(response["data"]) == 1
        mock_db.table.assert_called_with("compliance_rule")
