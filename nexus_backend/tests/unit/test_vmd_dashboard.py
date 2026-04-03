import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import Request
from app.routers.vmd_dashboard import get_model_usage, get_dashboard_stats

@pytest.mark.asyncio
class TestVMDDashboardUnit:
    """VMD 仪表盘路由单元测试"""

    async def test_get_model_usage_success(self):
        """测试获取模型用量统计成功路径"""
        mock_data = [
            {
                "model_code": "gpt-4",
                "total_input_tokens": 100,
                "total_output_tokens": 50,
                "total_calls": 10,
                "total_cost": 0.5
            },
            {
                "model_code": "gpt-4",
                "total_input_tokens": 200,
                "total_output_tokens": 100,
                "total_calls": 20,
                "total_cost": 1.0
            }
        ]
        
        mock_res = MagicMock()
        mock_res.data = mock_data
        
        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.neq.return_value = mock_query
        mock_query.execute = AsyncMock(return_value=mock_res)
        
        mock_db = MagicMock()
        mock_db.table.return_value = mock_query
        
        mock_req = MagicMock(spec=Request)
        mock_req.state.db = mock_db
        mock_req.state.org_id = "org-123"

        response = await get_model_usage(mock_req, user_id="user-123")
        
        assert response["success"] is True
        usage = response["data"]["usage"]
        assert len(usage) == 1
        assert usage[0]["model_code"] == "gpt-4"
        assert usage[0]["total_input_tokens"] == 300
        assert usage[0]["call_count"] == 30
        assert pytest.approx(usage[0]["total_cost"]) == 1.5

    async def test_get_dashboard_stats_success(self):
        """测试获取仪表盘概览统计成功"""
        # Mock clues count
        clues_res = MagicMock()
        clues_res.count = 50
        
        # Mock tasks count
        tasks_res = MagicMock()
        tasks_res.count = 5
        
        # Mock compliance count
        compliance_res = MagicMock()
        compliance_res.count = 2
        
        # Mock agents count
        agents_res = MagicMock()
        agents_res.count = 3
        
        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.neq.return_value = mock_query
        mock_query.eq.return_value = mock_query
        # Sequential execute calls
        mock_query.execute = AsyncMock(side_effect=[clues_res, tasks_res, compliance_res, agents_res])
        
        mock_db = MagicMock()
        mock_db.table.return_value = mock_query
        
        mock_req = MagicMock(spec=Request)
        mock_req.state.db = mock_db

        response = await get_dashboard_stats(mock_req, user_id="user-123")
        
        assert response["success"] is True
        assert response["data"]["clues_count"] == 50
        assert response["data"]["tasks_count"] == 5
        assert response["data"]["compliance_issues"] == 2
        assert response["data"]["active_agents"] == 3
