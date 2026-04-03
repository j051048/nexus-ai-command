import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import Request, HTTPException
from app.routers.vmd_tasks import (
    list_vmd_tasks, 
    get_vmd_task_detail, 
    pause_vmd_task, 
    resume_vmd_task, 
    cancel_vmd_task, 
    list_vmd_sub_tasks
)

@pytest.mark.asyncio
class TestVMDTasksUnit:
    """VMD 任务路由单元测试"""

    async def test_list_vmd_tasks_success(self):
        """测试获取任务列表成功路径"""
        mock_data = [
            {"id": "t1", "task_name": "Task 1"},
            {"id": "t2", "task_name": "Task 2"}
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
        mock_req.state.db = mock_db

        response = await list_vmd_tasks(mock_req, user_id="user-123")
        
        assert response["success"] is True
        assert len(response["data"]["tasks"]) == 2

    async def test_get_vmd_task_detail_success(self):
        """测试获取任务详情成功路径"""
        mock_res = MagicMock()
        mock_res.data = {"id": "task-abc", "task_code": "TSK-001", "task_name": "Task Detail"}
        
        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.maybe_single.return_value = mock_query
        mock_query.execute = AsyncMock(return_value=mock_res)
        
        mock_db = MagicMock()
        mock_db.table.return_value = mock_query
        
        mock_req = MagicMock(spec=Request)
        mock_req.state.db = mock_db

        response = await get_vmd_task_detail(mock_req, task_id="TSK-001", user_id="user-123")
        
        assert response["success"] is True
        assert response["data"]["task_code"] == "TSK-001"

    async def test_pause_vmd_task_success(self):
        """测试暂停任务成功"""
        # 1. Mock first check (status=running)
        mock_check_res = MagicMock()
        mock_check_res.data = {"status": "running"}
        
        # 2. Mock update execution
        mock_update_res = MagicMock()
        mock_update_res.data = {"status": "paused"}

        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.maybe_single.return_value = mock_query
        mock_query.update.return_value = mock_query
        
        # We need the execute to return different things
        mock_query.execute = AsyncMock(side_effect=[mock_check_res, mock_update_res])
        
        mock_db = MagicMock()
        mock_db.table.return_value = mock_query
        
        mock_req = MagicMock(spec=Request)
        mock_req.state.db = mock_db

        response = await pause_vmd_task(mock_req, task_id="t1", user_id="user-123")
        
        assert response["success"] is True
        assert response["data"]["status"] == "paused"
        mock_query.update.assert_called_with({"status": "paused"})

    async def test_pause_vmd_task_invalid_status(self):
        """测试暂停非运行中任务应报错"""
        mock_check_res = MagicMock()
        mock_check_res.data = {"status": "completed"}
        
        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.maybe_single.return_value = mock_query
        mock_query.execute = AsyncMock(return_value=mock_check_res)
        
        mock_db = MagicMock()
        mock_db.table.return_value = mock_query
        
        mock_req = MagicMock(spec=Request)
        mock_req.state.db = mock_db

        with pytest.raises(HTTPException) as excinfo:
            await pause_vmd_task(mock_req, task_id="t1", user_id="user-123")
        
        assert excinfo.value.status_code == 400
        # Fix assertion to match actual message "只有进行中的任务可以暂停"
        assert "进行中" in excinfo.value.detail["message"]

    async def test_cancel_vmd_task_success(self):
        """测试取消任务成功"""
        mock_check_res = MagicMock()
        mock_check_res.data = {"status": "running"}
        
        mock_update_res = MagicMock()
        
        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.maybe_single.return_value = mock_query
        mock_query.update.return_value = mock_query
        mock_query.execute = AsyncMock(side_effect=[mock_check_res, mock_update_res])
        
        mock_db = MagicMock()
        mock_db.table.return_value = mock_query
        
        mock_req = MagicMock(spec=Request)
        mock_req.state.db = mock_db

        response = await cancel_vmd_task(mock_req, task_id="t1", user_id="user-123")
        
        assert response["success"] is True
        assert response["data"]["status"] == "cancelled"

    async def test_list_vmd_sub_tasks_success(self):
        """测试获取子任务审计日志"""
        mock_res = MagicMock()
        mock_res.data = [{"id": 1, "action": "search"}]
        
        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.execute = AsyncMock(return_value=mock_res)
        
        mock_db = MagicMock()
        mock_db.table.return_value = mock_query
        
        mock_req = MagicMock(spec=Request)
        mock_req.state.db = mock_db

        response = await list_vmd_sub_tasks(mock_req, task_id="t1", user_id="user-123")
        
        assert response["success"] is True
        assert len(response["data"]["sub_tasks"]) == 1
