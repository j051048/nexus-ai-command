"""
WorkflowTemplateService 单元测试
覆盖: 模板列表、获取、从模板创建工作流、分享模板
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.workflow_template_service import WorkflowTemplateService


class TestListTemplates:
    """模板列表测试"""

    def setup_method(self):
        self.svc = WorkflowTemplateService()

    @pytest.mark.asyncio
    async def test_list_includes_builtin(self):
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = []
        mock_db.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(return_value=resp)

        with patch("app.services.workflow_template_service.supabase", mock_db):
            result = await self.svc.list_templates(category=None, org_id="org-1", db=mock_db)
            assert isinstance(result, list)
            assert len(result) >= len(self.svc.BUILTIN_TEMPLATES)

    @pytest.mark.asyncio
    async def test_list_filter_by_category(self):
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = []
        mock_db.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(return_value=resp)

        with patch("app.services.workflow_template_service.supabase", mock_db):
            result = await self.svc.list_templates(category="finance", org_id="org-1", db=mock_db)
            for tpl in result:
                if tpl.get("is_builtin"):
                    assert tpl["category"] == "finance"


class TestGetTemplate:
    """获取单个模板测试"""

    def setup_method(self):
        self.svc = WorkflowTemplateService()

    @pytest.mark.asyncio
    async def test_get_builtin_template(self):
        result = await self.svc.get_template("tpl_expense")
        assert result is not None
        assert result["name"] == "费用报销标准流程"

    @pytest.mark.asyncio
    async def test_get_nonexistent_template(self):
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = None
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(return_value=resp)

        with patch("app.services.workflow_template_service.supabase", mock_db):
            result = await self.svc.get_template("nonexistent", db=mock_db)
            assert result is None


class TestCreateFromTemplate:
    """从模板创建工作流测试"""

    def setup_method(self):
        self.svc = WorkflowTemplateService()

    @pytest.mark.asyncio
    async def test_create_from_builtin(self):
        mock_db = MagicMock()
        create_resp = MagicMock()
        create_resp.data = [{"id": "wf-1", "name": "My Expense Flow"}]
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(return_value=create_resp)

        with patch("app.services.workflow_template_service.supabase", mock_db):
            result = await self.svc.create_workflow_from_template(
                "tpl_expense", "org-1", "My Expense Flow", "user-1", db=mock_db
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_create_from_nonexistent_raises(self):
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = None
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(return_value=resp)

        with patch("app.services.workflow_template_service.supabase", mock_db), pytest.raises(ValueError):
            await self.svc.create_workflow_from_template(
                "nonexistent", "org-1", "Test", "user-1", db=mock_db
            )


class TestCategories:
    """分类列表测试"""

    def test_get_categories(self):
        svc = WorkflowTemplateService()
        cats = svc.get_categories()
        assert isinstance(cats, dict)
        assert len(cats) > 0
