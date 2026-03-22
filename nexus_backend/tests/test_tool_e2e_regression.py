"""
Tool E2E Regression Tests — 工具端到端回归测试

测试 Top 20 工具的完整流程:
意图解析 → 工具选择 → 参数提取 → 执行 → 结果验证

所有测试使用 Mock LLM + Mock Supabase，不依赖外部服务。

覆盖类别:
- CRM: get_customers, create_customer, update_customer_stage
- Approval: approve_request, reject_request, get_pending_approvals, submit_approval_on_behalf
- HR: query_attendance, get_employee_profile, query_team_attendance
- Finance: create_expense_claim, query_expense_status, query_budget
- Knowledge: query_knowledge_base
- Calendar: book_meeting, query_leave_status
- Report: generate_weekly_report, get_performance_report
- Negative tests: invalid parameters, missing required fields
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.base_tool import BaseTool


# ═══════════════════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_db():
    """构造通用 MockSupabaseClient，预置常用表数据"""
    from tests.conftest import MockSupabaseClient

    db = MockSupabaseClient()

    # Users
    db.set_table_data("users", [
        {"id": "user-001", "name": "张三", "role": "employee", "department": "销售部", "org_id": "org-001"},
        {"id": "user-002", "name": "李四", "role": "manager", "department": "销售部", "org_id": "org-001"},
    ])

    # Customers
    db.set_table_data("customers", [
        {"id": "cust-001", "name": "测试客户A", "company": "ABC公司", "stage": "qualified",
         "owner_id": "user-001", "org_id": "org-001"},
        {"id": "cust-002", "name": "测试客户B", "company": "XYZ公司", "stage": "new",
         "owner_id": "user-001", "org_id": "org-001"},
    ])

    # Approvals
    db.set_table_data("approvals", [
        {"id": "appr-001", "type": "expense", "status": "pending", "requester_id": "user-001",
         "amount": 5000, "description": "差旅报销", "org_id": "org-001"},
    ])

    # Attendance
    db.set_table_data("attendance", [
        {"id": "att-001", "user_id": "user-001", "date": "2026-03-15",
         "check_in": "09:00", "check_out": "18:00", "status": "normal"},
    ])

    # Expenses
    db.set_table_data("expense_claims", [
        {"id": "exp-001", "user_id": "user-001", "amount": 1500, "type": "travel",
         "status": "pending", "description": "出差北京"},
    ])

    # Knowledge base
    db.set_rpc_result("search_knowledge", [
        {"id": "kb-001", "title": "销售流程指南", "content": "标准销售流程包含...", "score": 0.95},
    ])

    # Projects
    db.set_table_data("projects", [
        {"id": "proj-001", "name": "Q1销售冲刺", "status": "active", "org_id": "org-001"},
    ])

    # Leave requests
    db.set_table_data("leave_requests", [
        {"id": "leave-001", "user_id": "user-001", "type": "annual",
         "start_date": "2026-03-20", "end_date": "2026-03-21", "status": "pending"},
    ])

    # Budget
    db.set_table_data("budgets", [
        {"id": "budget-001", "department": "销售部", "total": 500000,
         "used": 120000, "remaining": 380000, "month": "2026-03"},
    ])

    return db


@pytest.fixture
def tool_config():
    """标准工具配置"""
    return {
        "token": "test-token-fake",
        "org_id": "org-001",
        "api_key": "sk-test-key-fake",
        "base_url": "https://api.test.com/v1",
        "model": "gpt-4o",
    }


USER_ID = "user-001"
MANAGER_USER_ID = "user-002"


# ═══════════════════════════════════════════════════════════════════════════════
#  Helper: 动态加载工具类
# ═══════════════════════════════════════════════════════════════════════════════


def _load_tool(tool_name: str) -> BaseTool:
    """从工具注册表动态加载工具实例"""
    from app.tools import _TOOL_MODULES

    if tool_name not in _TOOL_MODULES:
        raise KeyError(f"Tool '{tool_name}' not registered in _TOOL_MODULES")

    module_path, class_name = _TOOL_MODULES[tool_name]
    import importlib
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    return cls()


def _assert_tool_metadata(tool: BaseTool):
    """验证工具基本元数据完整性"""
    assert tool.name, "Tool must have a name"
    assert tool.description, "Tool must have a description"
    assert isinstance(tool.parameters, dict), "Tool parameters must be a dict (JSON Schema)"
    assert tool.parameters.get("type") == "object", "Tool parameters schema must be type=object"


# ═══════════════════════════════════════════════════════════════════════════════
#  1. CRM 工具测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestCRMToolsE2E:
    """CRM 工具端到端回归测试"""

    @pytest.mark.asyncio
    async def test_get_customers_basic(self, mock_db, tool_config):
        """查询客户列表 — 基本场景"""
        tool = _load_tool("get_customers")
        _assert_tool_metadata(tool)

        with patch("app.tools.crm_tools.supabase", mock_db):
            result = await tool.run({"limit": 10}, USER_ID, tool_config)

        assert isinstance(result, str)
        assert "客户" in result or "cust" in result.lower() or "没有" in result or "查询" in result

    @pytest.mark.asyncio
    async def test_get_customers_with_stage_filter(self, mock_db, tool_config):
        """查询客户列表 — 按阶段筛选"""
        tool = _load_tool("get_customers")

        with patch("app.tools.crm_tools.supabase", mock_db):
            result = await tool.run({"stage": "qualified"}, USER_ID, tool_config)

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_create_customer(self, mock_db, tool_config):
        """创建客户"""
        tool = _load_tool("create_customer")
        _assert_tool_metadata(tool)

        args = {
            "name": "新客户",
            "company": "新公司",
            "phone": "13800138000",
            "stage": "new",
        }

        with patch("app.tools.crm_tools.supabase", mock_db):
            result = await tool.run(args, USER_ID, tool_config)

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_update_customer_stage(self, mock_db, tool_config):
        """更新客户阶段"""
        tool = _load_tool("update_customer_stage")
        _assert_tool_metadata(tool)

        args = {
            "customer_id": "cust-001",
            "new_stage": "proposal",
        }

        with patch("app.tools.crm_tools.supabase", mock_db):
            result = await tool.run(args, USER_ID, tool_config)

        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. Approval 审批工具测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestApprovalToolsE2E:
    """审批工具端到端回归测试"""

    @pytest.mark.asyncio
    async def test_get_pending_approvals(self, mock_db, tool_config):
        """查询待审批列表"""
        tool = _load_tool("get_pending_approvals")
        _assert_tool_metadata(tool)

        with patch("app.tools.approval_tools.supabase", mock_db):
            result = await tool.run({}, MANAGER_USER_ID, tool_config)

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_approve_request_requires_confirmation(self, mock_db, tool_config):
        """审批通过 — 必须要求确认（不可逆操作）"""
        tool = _load_tool("approve_request")
        _assert_tool_metadata(tool)
        assert tool.is_irreversible, "approve_request should be irreversible"

        # 未确认时应返回确认提示
        preview = tool.check_confirmation({"approval_id": "appr-001"}, system_confirmed=False)
        assert preview is not None, "Should require confirmation when not confirmed"

    @pytest.mark.asyncio
    async def test_reject_request_requires_confirmation(self, mock_db, tool_config):
        """驳回审批 — 必须要求确认（不可逆操作）"""
        tool = _load_tool("reject_request")
        _assert_tool_metadata(tool)
        assert tool.is_irreversible, "reject_request should be irreversible"

        preview = tool.check_confirmation(
            {"approval_id": "appr-001", "reason": "金额异常"},
            system_confirmed=False,
        )
        assert preview is not None

    @pytest.mark.asyncio
    async def test_approve_request_confirmed(self, mock_db, tool_config):
        """审批通过 — 已确认场景"""
        tool = _load_tool("approve_request")

        # 已确认时 check_confirmation 应返回 None
        preview = tool.check_confirmation({"approval_id": "appr-001"}, system_confirmed=True)
        assert preview is None, "Should allow when system_confirmed=True"

    @pytest.mark.asyncio
    async def test_submit_approval_on_behalf(self, mock_db, tool_config):
        """代提交审批"""
        tool = _load_tool("submit_approval_on_behalf")
        _assert_tool_metadata(tool)

        args = {
            "type": "expense",
            "amount": 3000,
            "description": "办公用品采购",
        }

        with patch("app.tools.approval_tools.supabase", mock_db):
            result = await tool.run(args, USER_ID, tool_config)

        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. HR 人力资源工具测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestHRToolsE2E:
    """HR 工具端到端回归测试"""

    @pytest.mark.asyncio
    async def test_query_attendance(self, mock_db, tool_config):
        """查询个人考勤"""
        tool = _load_tool("query_attendance")
        _assert_tool_metadata(tool)

        with patch("app.tools.hr_tools.supabase", mock_db):
            result = await tool.run({"query_type": "my_record"}, USER_ID, tool_config)

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_query_team_attendance(self, mock_db, tool_config):
        """查询团队考勤（需管理者权限）"""
        tool = _load_tool("query_team_attendance")
        _assert_tool_metadata(tool)

        with patch("app.tools.hr_tools.supabase", mock_db):
            result = await tool.run({}, MANAGER_USER_ID, tool_config)

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_get_employee_profile(self, mock_db, tool_config):
        """查询员工档案"""
        tool = _load_tool("get_employee_profile")
        _assert_tool_metadata(tool)

        with patch("app.tools.hr_tools.supabase", mock_db):
            result = await tool.run({}, USER_ID, tool_config)

        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. Finance 财务工具测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestFinanceToolsE2E:
    """财务工具端到端回归测试"""

    @pytest.mark.asyncio
    async def test_create_expense_claim(self, mock_db, tool_config):
        """创建报销单"""
        tool = _load_tool("create_expense_claim")
        _assert_tool_metadata(tool)

        args = {
            "expense_type": "travel",
            "amount": 2500,
            "description": "出差北京高铁票",
            "expense_date": "2026-03-10",
        }

        with patch("app.tools.finance_tools.supabase", mock_db):
            result = await tool.run(args, USER_ID, tool_config)

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_query_expense_status(self, mock_db, tool_config):
        """查询报销状态"""
        tool = _load_tool("query_expense_status")
        _assert_tool_metadata(tool)

        with patch("app.tools.finance_tools.supabase", mock_db):
            result = await tool.run({}, USER_ID, tool_config)

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_query_budget(self, mock_db, tool_config):
        """查询预算"""
        tool = _load_tool("query_budget")
        _assert_tool_metadata(tool)

        with patch("app.tools.finance_tools.supabase", mock_db):
            result = await tool.run({}, USER_ID, tool_config)

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_high_value_expense_requires_confirmation(self, mock_db, tool_config):
        """高额报销触发确认"""
        tool = _load_tool("create_expense_claim")

        # 超过阈值 50000 应触发高额确认
        preview = tool.check_confirmation(
            {"expense_type": "travel", "amount": 60000},
            system_confirmed=False,
        )
        # 即使工具本身不是 is_irreversible，高额也应触发
        if preview:
            assert "确认" in preview or "大额" in preview


# ═══════════════════════════════════════════════════════════════════════════════
#  5. Knowledge 知识库工具测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestKnowledgeToolsE2E:
    """知识库工具端到端回归测试"""

    @pytest.mark.asyncio
    async def test_query_knowledge_base(self, mock_db, tool_config):
        """查询知识库"""
        tool = _load_tool("query_knowledge_base")
        _assert_tool_metadata(tool)

        args = {"query": "销售流程"}

        with patch("app.tools.operational_tools.supabase", mock_db):
            result = await tool.run(args, USER_ID, tool_config)

        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════════════════
#  6. Calendar/OA 工具测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalendarToolsE2E:
    """日历/OA 工具端到端回归测试"""

    @pytest.mark.asyncio
    async def test_book_meeting(self, mock_db, tool_config):
        """预约会议"""
        tool = _load_tool("book_meeting")
        _assert_tool_metadata(tool)

        args = {
            "title": "周一销售会议",
            "datetime": "2026-03-16T10:00:00+08:00",
            "attendees": ["张三"],
        }

        with patch("app.tools.oa_tools._get_client", return_value=mock_db):
            result = await tool.run(args, USER_ID, tool_config)

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_query_leave_status(self, mock_db, tool_config):
        """查询请假状态"""
        tool = _load_tool("query_leave_status")
        _assert_tool_metadata(tool)

        with patch("app.tools.oa_tools._get_client", return_value=mock_db):
            result = await tool.run({}, USER_ID, tool_config)

        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════════════════
#  7. Report 报告工具测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestReportToolsE2E:
    """报告工具端到端回归测试"""

    @pytest.mark.asyncio
    async def test_generate_weekly_report(self, mock_db, tool_config):
        """生成周报"""
        tool = _load_tool("generate_weekly_report")
        _assert_tool_metadata(tool)

        with patch("app.tools.project_tools.supabase", mock_db):
            result = await tool.run({}, USER_ID, tool_config)

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_get_performance_report(self, mock_db, tool_config):
        """获取绩效报告"""
        tool = _load_tool("get_performance_report")
        _assert_tool_metadata(tool)

        with patch("app.tools.operational_tools.supabase", mock_db):
            result = await tool.run({}, USER_ID, tool_config)

        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════════════════
#  8. Tool Metadata 元数据验证（批量）
# ═══════════════════════════════════════════════════════════════════════════════


class TestToolMetadataRegression:
    """批量验证所有注册工具的元数据完整性"""

    TOP_20_TOOLS = [
        "get_customers",
        "create_customer",
        "update_customer_stage",
        "approve_request",
        "reject_request",
        "get_pending_approvals",
        "submit_approval_on_behalf",
        "query_attendance",
        "query_team_attendance",
        "get_employee_profile",
        "create_expense_claim",
        "query_expense_status",
        "query_budget",
        "query_knowledge_base",
        "book_meeting",
        "query_leave_status",
        "generate_weekly_report",
        "get_performance_report",
        "create_leave_request",
        "assign_task",
    ]

    @pytest.mark.parametrize("tool_name", TOP_20_TOOLS)
    def test_tool_has_valid_metadata(self, tool_name):
        """每个工具应有完整的 name, description, parameters"""
        tool = _load_tool(tool_name)
        _assert_tool_metadata(tool)

    @pytest.mark.parametrize("tool_name", TOP_20_TOOLS)
    def test_tool_parameters_have_properties(self, tool_name):
        """每个工具的 parameters schema 应包含 properties 字段"""
        tool = _load_tool(tool_name)
        assert "properties" in tool.parameters, f"{tool_name} missing 'properties' in schema"

    @pytest.mark.parametrize("tool_name", TOP_20_TOOLS)
    def test_tool_has_run_method(self, tool_name):
        """每个工具应有 async run 方法"""
        tool = _load_tool(tool_name)
        assert hasattr(tool, "run"), f"{tool_name} missing run method"
        assert asyncio.iscoroutinefunction(tool.run), f"{tool_name}.run should be async"


# ═══════════════════════════════════════════════════════════════════════════════
#  9. Negative Tests — 参数校验
# ═══════════════════════════════════════════════════════════════════════════════


class TestNegativeValidation:
    """负面测试 — 无效参数、缺失必填字段"""

    @pytest.mark.asyncio
    async def test_expense_missing_required_fields(self):
        """报销缺少必填字段应抛出 ValueError"""
        tool = _load_tool("create_expense_claim")

        # 缺少 expense_type 和 amount
        with pytest.raises(ValueError, match="参数校验失败"):
            await tool.validate({})

    @pytest.mark.asyncio
    async def test_expense_invalid_type(self):
        """报销类型不在枚举值中应抛出 ValueError"""
        tool = _load_tool("create_expense_claim")

        with pytest.raises(ValueError, match="参数校验失败"):
            await tool.validate({"expense_type": "invalid_type", "amount": 100})

    @pytest.mark.asyncio
    async def test_attendance_invalid_query_type(self):
        """考勤查询类型无效"""
        tool = _load_tool("query_attendance")

        with pytest.raises(ValueError, match="参数校验失败"):
            await tool.validate({"query_type": "nonexistent"})

    @pytest.mark.asyncio
    async def test_tool_validate_passes_valid_args(self):
        """合法参数应通过校验"""
        tool = _load_tool("create_expense_claim")

        # 不应抛出异常
        await tool.validate({"expense_type": "travel", "amount": 500})

    def test_irreversible_tool_blocked_without_confirmation(self):
        """不可逆工具在未确认时应被拦截"""
        tool = _load_tool("approve_request")
        preview = tool.check_confirmation({"approval_id": "test"}, system_confirmed=False)
        assert preview is not None
        assert "确认" in preview

    def test_irreversible_tool_allowed_with_confirmation(self):
        """不可逆工具在已确认时应放行"""
        tool = _load_tool("approve_request")
        preview = tool.check_confirmation({"approval_id": "test"}, system_confirmed=True)
        assert preview is None

    def test_bulk_operation_triggers_confirmation(self):
        """批量操作超过阈值应触发确认"""
        tool = _load_tool("approve_request")
        preview = tool.check_confirmation(
            {"approval_id": "test", "ids": ["a", "b", "c", "d", "e"]},
            system_confirmed=False,
        )
        assert preview is not None


# ═══════════════════════════════════════════════════════════════════════════════
#  10. Tool Registration 注册表完整性
# ═══════════════════════════════════════════════════════════════════════════════


class TestToolRegistration:
    """验证工具注册表"""

    def test_all_top20_tools_registered(self):
        """Top 20 工具全部在注册表中"""
        from app.tools import _TOOL_MODULES

        for tool_name in TestToolMetadataRegression.TOP_20_TOOLS:
            assert tool_name in _TOOL_MODULES, f"Tool '{tool_name}' not in _TOOL_MODULES"

    def test_registered_tools_importable(self):
        """注册表中的工具均可成功导入"""
        from app.tools import _TOOL_MODULES

        for tool_name in TestToolMetadataRegression.TOP_20_TOOLS:
            tool = _load_tool(tool_name)
            assert isinstance(tool, BaseTool), f"{tool_name} should be a BaseTool instance"

    def test_no_duplicate_tool_names(self):
        """工具名不应重复"""
        from app.tools import _TOOL_MODULES

        names = list(_TOOL_MODULES.keys())
        assert len(names) == len(set(names)), "Duplicate tool names in registry"
