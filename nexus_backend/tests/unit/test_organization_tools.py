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
        tree_root = MagicMock()
        tree_root.name = "总部"
        tree_root.metadata = {"manager_id": str(uuid.uuid4())}
        tree_root.children = []
        with (
            patch("app.tools.organization_tools._get_client", return_value=_mock_client()),
            patch("app.tools.organization_tools.org_hierarchy_service") as svc,
            patch("app.tools.organization_tools.organization_service") as org_svc,
        ):
            svc.get_department_tree = AsyncMock(return_value=[tree_root])
            org_svc.get_org_statistics = AsyncMock(return_value={"total_employees": 10, "total_departments": 1})
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "总部" in result or "10 名员工" in result

class TestGetEmployeeDetailTool:
    @pytest.mark.asyncio
    async def test_get_employee_detail_success(self):
        tool = _load_tool("get_employee_detail")
        emp_id = str(uuid.uuid4())
        mock_emp = {"id": emp_id, "name": "张三", "status": "active"}
        with (
            patch("app.tools.organization_tools._get_client", return_value=_mock_client()),
            patch("app.tools.organization_tools.organization_service") as svc,
        ):
            svc.get_employee_detail = AsyncMock(return_value=mock_emp)
            result = await tool.run({"employee_id": emp_id}, FAKE_USER_ID, CONFIG)
        assert "张三" in result
        
    @pytest.mark.asyncio
    async def test_get_employee_detail_not_found(self):
        tool = _load_tool("get_employee_detail")
        with (
            patch("app.tools.organization_tools._get_client", return_value=_mock_client()),
            patch("app.tools.organization_tools.organization_service") as svc,
        ):
            svc.get_employee_detail = AsyncMock(return_value=None)
            result = await tool.run({"employee_id": str(uuid.uuid4())}, FAKE_USER_ID, CONFIG)
        assert "不存在" in result or "❌" in result

class TestCreateEmployeeTool:
    @pytest.mark.asyncio
    async def test_create_employee_success(self):
        tool = _load_tool("create_employee")
        new_emp = {"id": str(uuid.uuid4()), "name": "新员工"}
        with (
            patch("app.tools.organization_tools._get_client", return_value=_mock_client()),
            patch("app.tools.organization_tools.organization_service") as svc,
        ):
            svc.create_employee = AsyncMock(return_value=new_emp)
            result = await tool.run({"name": "新员工", "department_id": str(uuid.uuid4()), "position_id": str(uuid.uuid4()), "email": "test@test.com"}, FAKE_USER_ID, CONFIG)
        assert "✅" in result or "新员工" in result

    @pytest.mark.asyncio
    async def test_create_employee_missing_fields(self):
        tool = _load_tool("create_employee")
        with patch("app.tools.organization_tools._get_client", return_value=_mock_client()):
            result = await tool.run({"name": "新员工"}, FAKE_USER_ID, CONFIG)
        assert "❌" in result or "不能为空" in result

class TestUpdateEmployeeTool:
    @pytest.mark.asyncio
    async def test_update_employee_success(self):
        tool = _load_tool("update_employee")
        emp_id = str(uuid.uuid4())
        updated_emp = {"id": emp_id, "status": "resigned"}
        with (
            patch("app.tools.organization_tools._get_client", return_value=_mock_client()),
            patch("app.tools.organization_tools.organization_service") as svc,
        ):
            svc.update_employee = AsyncMock(return_value=updated_emp)
            result = await tool.run({"employee_id": emp_id, "status": "resigned"}, FAKE_USER_ID, CONFIG)
        result_str = str(result)
        assert "✅" in result_str or "已更新" in result_str

    @pytest.mark.asyncio
    async def test_update_employee_no_fields(self):
        tool = _load_tool("update_employee")
        with patch("app.tools.organization_tools._get_client", return_value=_mock_client()):
            result = await tool.run({"employee_id": str(uuid.uuid4())}, FAKE_USER_ID, CONFIG)
        assert "❌" in result or "至少" in result

class TestGetReportingLineTool:
    @pytest.mark.asyncio
    async def test_get_reporting_line_success(self):
        tool = _load_tool("get_reporting_line")
        emp_id = str(uuid.uuid4())
        mock_line = [{"id": emp_id, "name": "员工A"}, {"id": str(uuid.uuid4()), "name": "经理B"}]
        with (
            patch("app.tools.organization_tools._get_client", return_value=_mock_client()),
            patch("app.tools.organization_tools.org_hierarchy_service.get_user_reporting_line", new_callable=AsyncMock) as mock_get_line,
        ):
            mock_get_line.return_value = mock_line
            result = await tool.run({"user_id": emp_id}, FAKE_USER_ID, CONFIG)
        result_str = str(result)
        assert "汇报线" in result_str or "员工A" in result_str
        
    @pytest.mark.asyncio
    async def test_get_reporting_line_empty(self):
        tool = _load_tool("get_reporting_line")
        with (
            patch("app.tools.organization_tools._get_client", return_value=_mock_client()),
            patch("app.tools.organization_tools.org_hierarchy_service.get_user_reporting_line", new_callable=AsyncMock) as mock_get_line,
        ):
            mock_get_line.return_value = []
            result = await tool.run({"user_id": str(uuid.uuid4())}, FAKE_USER_ID, CONFIG)
        result_str = str(result)
        assert "没有" in result_str or "❌" in result_str

class TestOrganizationToolsCoverageExtra:
    @pytest.mark.asyncio
    async def test_list_departments_error(self):
        tool = _load_tool("list_departments")
        with patch("app.tools.organization_tools._get_client"), patch("app.tools.organization_tools.organization_service") as svc:
            svc.list_departments = AsyncMock(side_effect=Exception("DB Error"))
            res = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "error" in str(res).lower() or "失败" in str(res)



    @pytest.mark.asyncio
    async def test_update_department_error(self):
        tool = _load_tool("update_department")
        with patch("app.tools.organization_tools._get_client"), patch("app.tools.organization_tools.organization_service") as svc:
            svc.update_department = AsyncMock(side_effect=Exception("DB Error"))
            res = await tool.run({"department_id": str(uuid.uuid4()), "name": "New"}, FAKE_USER_ID, CONFIG)
        assert "error" in str(res).lower() or "失败" in str(res)

    @pytest.mark.asyncio
    async def test_list_employees_error(self):
        tool = _load_tool("list_employees")
        with patch("app.tools.organization_tools._get_client"), patch("app.tools.organization_tools.organization_service") as svc:
            svc.list_employees = AsyncMock(side_effect=Exception("DB Error"))
            res = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "error" in str(res).lower() or "失败" in str(res)

    @pytest.mark.asyncio
    async def test_get_employee_detail_error(self):
        tool = _load_tool("get_employee_detail")
        with patch("app.tools.organization_tools._get_client"), patch("app.tools.organization_tools.organization_service") as svc:
            svc.get_employee_detail = AsyncMock(side_effect=Exception("DB Error"))
            res = await tool.run({"employee_id": str(uuid.uuid4())}, FAKE_USER_ID, CONFIG)
        assert "error" in str(res).lower() or "失败" in str(res)

    @pytest.mark.asyncio
    async def test_get_org_tree_error(self):
        tool = _load_tool("get_org_tree")
        with patch("app.tools.organization_tools._get_client"), patch("app.tools.organization_tools.org_hierarchy_service") as svc:
            svc.get_department_tree = AsyncMock(side_effect=Exception("DB Error"))
            res = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "error" in str(res).lower() or "失败" in str(res)

    @pytest.mark.asyncio
    async def test_list_departments_edge_cases(self):
        tool = _load_tool("list_departments")
        with patch("app.tools.organization_tools._get_client", return_value=_mock_client()):
            res = await tool.run({}, FAKE_USER_ID, {})
        assert "❌" in str(res)

    @pytest.mark.asyncio
    async def test_create_department_edge_cases(self):
        tool = _load_tool("create_department")
        with patch("app.tools.organization_tools._get_client", return_value=_mock_client()):
            res = await tool.run({"name": "Test"}, FAKE_USER_ID, {})
        assert "❌" in str(res)
        res = await tool.run({"name": "Test", "parent_id": "invalid"}, FAKE_USER_ID, CONFIG)
        assert "❌" in str(res)
        res = await tool.run({"name": "Test", "manager_id": "invalid"}, FAKE_USER_ID, CONFIG)
        assert "❌" in str(res)

    @pytest.mark.asyncio
    async def test_update_department_edge_cases(self):
        tool = _load_tool("update_department")
        with patch("app.tools.organization_tools._get_client", return_value=_mock_client()):
            res = await tool.run({"department_id": str(uuid.uuid4()), "name": "New"}, FAKE_USER_ID, {})
        assert "❌" in str(res)
        with patch("app.tools.organization_tools._get_client", return_value=_mock_client()):
            res = await tool.run({"department_id": str(uuid.uuid4()), "manager_id": "invalid"}, FAKE_USER_ID, CONFIG)
        assert "❌" in str(res)
        with patch("app.tools.organization_tools._get_client"), patch("app.tools.organization_tools.organization_service") as svc:
            svc.update_department = AsyncMock(return_value={"id": str(uuid.uuid4()), "name": "HR"})
            res = await tool.run({"department_id": str(uuid.uuid4()), "status": "active"}, FAKE_USER_ID, CONFIG)
        assert "HR" in str(res)

    @pytest.mark.asyncio
    async def test_list_employees_edge_cases(self):
        tool = _load_tool("list_employees")
        with patch("app.tools.organization_tools._get_client", return_value=_mock_client()):
            res = await tool.run({}, FAKE_USER_ID, {})
        assert "❌" in str(res)
        with patch("app.tools.organization_tools._get_client", return_value=_mock_client()):
            res = await tool.run({"department_id": "invalid"}, FAKE_USER_ID, CONFIG)
        assert "❌" in str(res)
        with patch("app.tools.organization_tools._get_client", return_value=_mock_client()):
            res = await tool.run({"position_id": "invalid"}, FAKE_USER_ID, CONFIG)
        assert "❌" in str(res)
        with patch("app.tools.organization_tools._get_client"), patch("app.tools.organization_tools.organization_service") as svc:
            svc.list_employees = AsyncMock(return_value=[])
            res = await tool.run({"search": "test", "status": "active"}, FAKE_USER_ID, CONFIG)
        assert "暂无" in str(res) or "没有" in str(res) or "❌" in str(res)
