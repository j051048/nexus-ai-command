"""
WorkflowDefinitionService 单元测试
覆盖: DAG 验证（纯同步）、工作流 CRUD
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.workflow_definition_service import (
    WorkflowDefinitionService,
)


class TestDAGValidation:
    """DAG 验证测试（纯同步，无需 mock）"""

    def setup_method(self):
        self.svc = WorkflowDefinitionService()

    def test_valid_linear_workflow(self):
        steps = [
            {"id": "s1", "type": "approver", "next": ["s2"]},
            {"id": "s2", "type": "notify", "next": []},
        ]
        errors = self.svc.validate_workflow_definition(steps, [])
        assert errors == []

    def test_invalid_node_type(self):
        steps = [{"id": "s1", "type": "invalid_type", "next": []}]
        errors = self.svc.validate_workflow_definition(steps, [])
        assert any("type" in e.lower() or "invalid" in e.lower() for e in errors)

    def test_orphan_reference(self):
        steps = [
            {"id": "s1", "type": "approver", "next": ["s_nonexistent"]},
        ]
        errors = self.svc.validate_workflow_definition(steps, [])
        assert len(errors) > 0

    def test_empty_steps(self):
        errors = self.svc.validate_workflow_definition([], [])
        assert len(errors) > 0

    def test_valid_parallel_workflow(self):
        steps = [
            {"id": "s1", "type": "parallel", "next": ["s2", "s3"]},
            {"id": "s2", "type": "approver", "next": ["s4"]},
            {"id": "s3", "type": "approver", "next": ["s4"]},
            {"id": "s4", "type": "end", "next": []},
        ]
        errors = self.svc.validate_workflow_definition(steps, [])
        assert errors == []


class TestWorkflowCRUD:
    """工作流 CRUD 测试"""

    def setup_method(self):
        self.svc = WorkflowDefinitionService()

    @pytest.mark.asyncio
    async def test_create_workflow(self):
        mock_db = MagicMock()
        # _get_valid_types
        type_resp = MagicMock()
        type_resp.data = [{"type_code": "expense"}]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute = AsyncMock(return_value=type_resp)
        # insert
        create_resp = MagicMock()
        create_resp.data = [{"id": "wf-1", "name": "Test WF"}]
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(return_value=create_resp)

        steps = [
            {"id": "s1", "type": "approver", "next": ["s2"]},
            {"id": "s2", "type": "end", "next": []},
        ]
        with patch("app.services.workflow_definition_service.supabase", mock_db):
            result = await self.svc.create_workflow(
                "org-1", "Test WF", ["expense"], steps, db=mock_db
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_create_no_db_raises(self):
        with patch("app.services.workflow_definition_service.supabase", None):
            with pytest.raises(ValueError, match="Database"):
                await self.svc.create_workflow("org-1", "Test", ["expense"], [], db=None)

    @pytest.mark.asyncio
    async def test_create_invalid_type_raises(self):
        mock_db = MagicMock()
        type_resp = MagicMock()
        type_resp.data = [{"type_code": "expense"}]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute = AsyncMock(return_value=type_resp)

        with patch("app.services.workflow_definition_service.supabase", mock_db):
            with pytest.raises(ValueError, match="Invalid approval type"):
                await self.svc.create_workflow("org-1", "Test", ["nonexistent"], [], db=mock_db)
