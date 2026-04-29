"""
组织架构工具 (organization_tools.py) 单元测试
覆盖：部门管理、员工管理、组织统计
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

FAKE_USER_ID = "user-" + "a" * 32
FAKE_ORG_ID = "org-" + "b" * 32
CONFIG = {"org_id": FAKE_ORG_ID, "token": "jwt-test"}


def _mock_client():
    """构建一个 mock supabase client，_get_client 返回此对象"""
    return MagicMock()


def _load_tool(name: str):
    from app.tools import get_tool
    tool = get_tool(name)
    assert tool is not None, f"Tool '{name}' not found in registry"
    return tool


# ════════════════════════════════════════════════════════════════════
# 部门列表
# ════════════════════════════════════════════════════════════════════


class TestListDepartmentsTool:
    """部门列表查询"""

    @pytest.mark.asyncio
    async def test_list_departments_success(self):
        tool = _load_tool("list_departments")
        mock_depts = [
            {"id": str(uuid.uuid4()), "name": "技术部", "manager": {"name": "张三"}},
            {"id": str(uuid.uuid4()), "name": "市场部", "manager": None},
        ]
        with (
            patch("app.tools.organization_tools._get_client", return_value=_mock_client()),
            patch("app.tools.organization_tools.organization_service") as svc,
        ):
            svc.list_departments = AsyncMock(return_value=mock_depts)
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "技术部" in result
        assert "市场部" in result
        assert "2" in result

    @pytest.mark.asyncio
    async def test_list_departments_empty(self):
        tool = _load_tool("list_departments")
        with (
            patch("app.tools.organization_tools._get_client", return_value=_mock_client()),
            patch("app.tools.organization_tools.organization_service") as svc,
        ):
            svc.list_departments = AsyncMock(return_value=[])
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "暂无" in result

    @pytest.mark.asyncio
    async def test_list_departments_with_parent(self):
        tool = _load_tool("list_departments")
        parent_id = str(uuid.uuid4())
        child_depts = [
            {"id": str(uuid.uuid4()), "name": "前端组", "manager": {"name": "李四"}},
        ]
        with (
            patch("app.tools.organization_tools._get_client", return_value=_mock_client()),
            patch("app.tools.organization_tools.organization_service") as svc,
        ):
            svc.list_departments = AsyncMock(return_value=child_depts)
            result = await tool.run({"parent_id": parent_id}, FAKE_USER_ID, CONFIG)
        assert "前端组" in result

    @pytest.mark.asyncio
    async def test_list_departments_invalid_uuid(self):
        tool = _load_tool("list_departments")
        with patch("app.tools.organization_tools._get_client", return_value=_mock_client()):
            result = await tool.run({"parent_id": "not-a-uuid"}, FAKE_USER_ID, CONFIG)
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_list_departments_no_org(self):
        tool = _load_tool("list_departments")
        # 无 org_id 时 _get_org_id 返回 None，同时 mock _get_client 防止 PermissionError
        with patch("app.tools.organization_tools._get_client", return_value=_mock_client()):
            result = await tool.run({}, FAKE_USER_ID, {"token": "t"})
        # _get_org_id({"token":"t"}) → None → 返回无法获取组织
        assert "无法获取组织" in str(result) or "❌" in str(result)


# ════════════════════════════════════════════════════════════════════
# 创建部门
# ════════════════════════════════════════════════════════════════════


class TestCreateDepartmentTool:
    """创建部门"""

    @pytest.mark.asyncio
    async def test_create_department_success(self):
        tool = _load_tool("create_department")
        dept_id = str(uuid.uuid4())
        new_dept = {"id": dept_id, "name": "研发部"}
        with (
            patch("app.tools.organization_tools._get_client", return_value=_mock_client()),
            patch("app.tools.organization_tools.organization_service") as svc,
        ):
            svc.create_department = AsyncMock(return_value=new_dept)
            result = await tool.run({"name": "研发部"}, FAKE_USER_ID, CONFIG)
        assert "研发部" in result
        assert "✅" in result

    @pytest.mark.asyncio
    async def test_create_department_empty_name(self):
        tool = _load_tool("create_department")
        with patch("app.tools.organization_tools._get_client", return_value=_mock_client()):
            result = await tool.run({"name": ""}, FAKE_USER_ID, CONFIG)
        assert "❌" in result
        assert "不能为空" in result

    @pytest.mark.asyncio
    async def test_create_department_with_parent(self):
        tool = _load_tool("create_department")
        parent_id = str(uuid.uuid4())
        new_dept = {"id": str(uuid.uuid4()), "name": "测试组", "parent_id": parent_id}
        with (
            patch("app.tools.organization_tools._get_client", return_value=_mock_client()),
            patch("app.tools.organization_tools.organization_service") as svc,
        ):
            svc.create_department = AsyncMock(return_value=new_dept)
            result = await tool.run(
                {"name": "测试组", "parent_id": parent_id}, FAKE_USER_ID, CONFIG
            )
        assert "测试组" in result

    @pytest.mark.asyncio
    async def test_create_department_service_error(self):
        tool = _load_tool("create_department")
        with (
            patch("app.tools.organization_tools._get_client", return_value=_mock_client()),
            patch("app.tools.organization_tools.organization_service") as svc,
        ):
            svc.create_department = AsyncMock(side_effect=Exception("DB error"))
            result = await tool.run({"name": "失败部门"}, FAKE_USER_ID, CONFIG)
        assert "失败" in result or "❌" in result


# ════════════════════════════════════════════════════════════════════
# 更新部门
# ════════════════════════════════════════════════════════════════════


class TestUpdateDepartmentTool:
    """更新部门"""

    @pytest.mark.asyncio
    async def test_update_department_name(self):
        tool = _load_tool("update_department")
        dept_id = str(uuid.uuid4())
        updated = {"id": dept_id, "name": "新技术部"}
        with (
            patch("app.tools.organization_tools._get_client", return_value=_mock_client()),
            patch("app.tools.organization_tools.organization_service") as svc,
        ):
            svc.update_department = AsyncMock(return_value=updated)
            result = await tool.run(
                {"department_id": dept_id, "name": "新技术部"}, FAKE_USER_ID, CONFIG
            )
        result_str = str(result)
        assert "新技术部" in result_str or "更新" in result_str or "✅" in result_str

    @pytest.mark.asyncio
    async def test_update_department_invalid_id(self):
        tool = _load_tool("update_department")
        with patch("app.tools.organization_tools._get_client", return_value=_mock_client()):
            result = await tool.run(
                {"department_id": "invalid", "name": "测试"}, FAKE_USER_ID, CONFIG
            )
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_update_department_no_fields(self):
        tool = _load_tool("update_department")
        dept_id = str(uuid.uuid4())
        with patch("app.tools.organization_tools._get_client", return_value=_mock_client()):
            result = await tool.run(
                {"department_id": dept_id}, FAKE_USER_ID, CONFIG
            )
        assert "❌" in str(result) or "至少" in str(result)


# ════════════════════════════════════════════════════════════════════
# 组织统计
# ════════════════════════════════════════════════════════════════════


class TestOrgStatisticsTool:
    """组织统计"""

    @pytest.mark.asyncio
    async def test_org_statistics(self):
        tool = _load_tool("org_statistics")
        stats = {
            "total_employees": 120,
            "total_departments": 8,
            "active_employees": 115,
        }
        with (
            patch("app.tools.organization_tools._get_client", return_value=_mock_client()),
            patch("app.tools.organization_tools.organization_service") as svc,
        ):
            svc.get_org_statistics = AsyncMock(return_value=stats)
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "120" in result or "员工" in result

    @pytest.mark.asyncio
    async def test_org_statistics_no_org(self):
        tool = _load_tool("org_statistics")
        with patch("app.tools.organization_tools._get_client", return_value=_mock_client()):
            result = await tool.run({}, FAKE_USER_ID, {})
        assert "无法获取组织" in str(result) or "❌" in str(result)


# ════════════════════════════════════════════════════════════════════
# 员工管理
# ════════════════════════════════════════════════════════════════════


class TestListEmployeesTool:
    """员工列表"""

    @pytest.mark.asyncio
    async def test_list_employees_success(self):
        tool = _load_tool("list_employees")
        employees = [
            {"id": str(uuid.uuid4()), "name": "张三",
             "position": {"name": "工程师"},
             "department_id": str(uuid.uuid4()), "status": "active",
             "phone": "13800138000"},
            {"id": str(uuid.uuid4()), "name": "李四",
             "position": {"name": "设计师"},
             "department_id": str(uuid.uuid4()), "status": "active",
             "phone": "13900139000"},
        ]
        with (
            patch("app.tools.organization_tools._get_client", return_value=_mock_client()),
            patch("app.tools.organization_tools.organization_service") as svc,
        ):
            svc.list_employees = AsyncMock(return_value=employees)
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        result_str = str(result)
        assert "张三" in result_str or "2" in result_str

    @pytest.mark.asyncio
    async def test_list_employees_by_department(self):
        tool = _load_tool("list_employees")
        dept_id = str(uuid.uuid4())
        employees = [
            {"id": str(uuid.uuid4()), "name": "王五",
             "position": {"name": "前端"},
             "department_id": dept_id, "status": "active",
             "phone": "13700137000"},
        ]
        with (
            patch("app.tools.organization_tools._get_client", return_value=_mock_client()),
            patch("app.tools.organization_tools.organization_service") as svc,
        ):
            svc.list_employees = AsyncMock(return_value=employees)
            result = await tool.run({"department_id": dept_id}, FAKE_USER_ID, CONFIG)
        assert "王五" in str(result)


class TestGetOrgTreeTool:
    """组织树"""

    @pytest.mark.asyncio
    async def test_get_org_tree(self):
        tool = _load_tool("get_org_tree")
        tree = {
            "id": str(uuid.uuid4()), "name": "总部",
            "children": [
                {"id": str(uuid.uuid4()), "name": "技术部", "children": []},
                {"id": str(uuid.uuid4()), "name": "市场部", "children": []},
            ],
        }
        with (
            patch("app.tools.organization_tools._get_client", return_value=_mock_client()),
            patch("app.tools.organization_tools.organization_service") as svc,
        ):
            svc.get_org_tree = AsyncMock(return_value=tree)
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "总部" in result or "技术部" in result or "组织" in result
