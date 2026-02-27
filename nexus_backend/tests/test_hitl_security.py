"""
#4 — HITL Safety (人机协同安全测试)

测试人机协同确认门控:
- 不可逆工具 (is_irreversible=True) 且 system_confirmed=False -> 阻止
- 高金额 (>50000) 且 system_confirmed=False -> 阻止
- system_confirmed=True -> 允许
- LLM 无法伪造确认 (args 中的 confirm 参数被忽略)
- 批量操作 (>5 条记录) 无确认 -> 阻止
- RBAC: employee 调用 manager 专用工具 -> 阻止
"""

import pytest

from app.tools.base_tool import BaseTool, ConfirmationType, CONFIRMATION_THRESHOLDS


# ═══════════════════════════════════════════════════════════════════════════════
#  Helper: 测试用工具定义
# ═══════════════════════════════════════════════════════════════════════════════


class MockIrreversibleTool(BaseTool):
    """模拟不可逆操作工具 (如: 删除审批)"""

    @property
    def name(self) -> str:
        return "delete_approval"

    @property
    def description(self) -> str:
        return "删除审批记录"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {"id": {"type": "string"}}}

    @property
    def is_irreversible(self) -> bool:
        return True

    @property
    def confirmation_message(self) -> str:
        return "删除操作不可恢复，请确认。"

    async def run(self, args, user_id, config=None):
        return "已删除"


class MockNormalTool(BaseTool):
    """模拟普通工具 (无需确认)"""

    @property
    def name(self) -> str:
        return "query_data"

    @property
    def description(self) -> str:
        return "查询数据"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {"query": {"type": "string"}}}

    async def run(self, args, user_id, config=None):
        return "查询结果"


class MockManagerTool(BaseTool):
    """模拟需要 manager 权限的工具"""

    @property
    def name(self) -> str:
        return "manage_team"

    @property
    def description(self) -> str:
        return "管理团队"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    @property
    def required_role(self) -> str:
        return "manager"

    async def run(self, args, user_id, config=None):
        return "团队管理成功"


class MockBossTool(BaseTool):
    """模拟需要 boss 权限的工具"""

    @property
    def name(self) -> str:
        return "view_salary"

    @property
    def description(self) -> str:
        return "查看薪资"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    @property
    def required_role(self) -> str:
        return "boss"

    async def run(self, args, user_id, config=None):
        return "薪资数据"


# ═══════════════════════════════════════════════════════════════════════════════
#  确认门控测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfirmationGate:
    """测试 check_confirmation 方法"""

    def test_irreversible_tool_blocked_without_confirmation(self):
        """不可逆工具在未确认时应被阻止"""
        tool = MockIrreversibleTool()
        result = tool.check_confirmation(args={"id": "req-001"}, system_confirmed=False)

        assert result is not None  # 非 None 表示需要确认
        assert "不可逆" in result or "确认" in result

    def test_irreversible_tool_allowed_with_confirmation(self):
        """不可逆工具在 system_confirmed=True 时应允许"""
        tool = MockIrreversibleTool()
        result = tool.check_confirmation(args={"id": "req-001"}, system_confirmed=True)

        assert result is None  # None 表示允许执行

    def test_high_value_blocked_without_confirmation(self):
        """高金额操作在未确认时应被阻止"""
        tool = MockNormalTool()
        result = tool.check_confirmation(
            args={"amount": 100000},  # 超过 50000 阈值
            system_confirmed=False,
        )

        assert result is not None
        assert "大额" in result or "确认" in result

    def test_high_value_allowed_with_confirmation(self):
        """高金额操作在确认后应允许"""
        tool = MockNormalTool()
        result = tool.check_confirmation(
            args={"amount": 100000},
            system_confirmed=True,
        )

        assert result is None

    def test_normal_amount_not_blocked(self):
        """正常金额不应被阻止"""
        tool = MockNormalTool()
        result = tool.check_confirmation(
            args={"amount": 1000},  # 低于阈值
            system_confirmed=False,
        )

        assert result is None

    def test_bulk_operation_blocked(self):
        """批量操作 (>5 条记录) 在未确认时应被阻止"""
        tool = MockNormalTool()
        result = tool.check_confirmation(
            args={"ids": ["1", "2", "3", "4", "5", "6"]},  # 6 条记录
            system_confirmed=False,
        )

        assert result is not None
        assert "批量" in result or "确认" in result

    def test_bulk_operation_under_threshold_not_blocked(self):
        """少量批量操作不应被阻止"""
        tool = MockNormalTool()
        result = tool.check_confirmation(
            args={"ids": ["1", "2", "3"]},  # 3 条, 低于 5 阈值
            system_confirmed=False,
        )

        assert result is None

    def test_bulk_operation_allowed_with_confirmation(self):
        """批量操作在确认后应允许"""
        tool = MockNormalTool()
        result = tool.check_confirmation(
            args={"ids": ["1", "2", "3", "4", "5", "6"]},
            system_confirmed=True,
        )

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
#  LLM 无法伪造确认
# ═══════════════════════════════════════════════════════════════════════════════


class TestLLMCannotForgeConfirmation:
    """测试 LLM 无法通过参数绕过确认机制"""

    def test_confirm_in_args_ignored(self):
        """args 中的 confirm=True 不应绕过系统确认"""
        tool = MockIrreversibleTool()

        # LLM 试图在参数中传入 confirm=True
        result = tool.check_confirmation(
            args={"id": "req-001", "confirm": True},
            system_confirmed=False,  # 系统层面未确认
        )

        # 应该仍然被阻止 (因为 system_confirmed=False)
        assert result is not None

    def test_confirmed_in_args_ignored(self):
        """args 中的 confirmed=True 不应绕过系统确认"""
        tool = MockIrreversibleTool()

        result = tool.check_confirmation(
            args={"id": "req-001", "confirmed": True},
            system_confirmed=False,
        )

        assert result is not None

    def test_only_system_confirmed_matters(self):
        """只有 system_confirmed 参数决定是否放行"""
        tool = MockIrreversibleTool()

        # 系统确认 + LLM 参数 -> 放行
        result_confirmed = tool.check_confirmation(
            args={"id": "req-001", "confirm": False},
            system_confirmed=True,
        )
        assert result_confirmed is None

        # 系统未确认 + LLM 声称确认 -> 阻止
        result_not_confirmed = tool.check_confirmation(
            args={"id": "req-001", "confirm": True},
            system_confirmed=False,
        )
        assert result_not_confirmed is not None


# ═══════════════════════════════════════════════════════════════════════════════
#  RBAC 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestRBAC:
    """测试基于角色的工具访问控制"""

    async def test_employee_blocked_from_manager_tool(self):
        """employee 调用 manager 工具应被 RBAC 阻止"""
        from app.agent.nodes import _execute_single_tool
        from app.agent.state import AgentConfig, ToolCallRecord

        config = AgentConfig(
            user_id="user-001",
            user_role="employee",
            api_key="sk-fake",
        )

        record = ToolCallRecord(
            tool_name="manage_team",
            tool_args={},
            tool_call_id="tc-001",
        )

        # Mock get_tool 返回我们的 MockManagerTool
        from unittest.mock import patch

        with (
            patch("app.agent.nodes.get_tool", return_value=MockManagerTool()),
            patch("app.agent.nodes.tool_circuit_breaker") as mock_cb,
        ):
            mock_cb.allow_request.return_value = True
            result = await _execute_single_tool(record, config)

        assert result.status == "blocked"
        assert "权限" in result.result

    async def test_manager_allowed_manager_tool(self):
        """manager 应能调用 manager 工具"""
        from app.agent.nodes import _execute_single_tool
        from app.agent.state import AgentConfig, ToolCallRecord

        config = AgentConfig(
            user_id="user-002",
            user_role="manager",
            api_key="sk-fake",
            system_confirmed=True,
        )

        record = ToolCallRecord(
            tool_name="manage_team",
            tool_args={},
            tool_call_id="tc-002",
        )

        from unittest.mock import patch, AsyncMock

        with (
            patch("app.agent.nodes.get_tool", return_value=MockManagerTool()),
            patch("app.agent.nodes.tool_circuit_breaker") as mock_cb,
            patch("app.agent.nodes.record_tool_execution"),
        ):
            mock_cb.allow_request.return_value = True
            mock_cb.record_success = lambda: None
            result = await _execute_single_tool(record, config)

        assert result.status == "success"

    async def test_employee_blocked_from_boss_tool(self):
        """employee 调用 boss 工具应被阻止"""
        from app.agent.nodes import _execute_single_tool
        from app.agent.state import AgentConfig, ToolCallRecord

        config = AgentConfig(
            user_id="user-003",
            user_role="employee",
            api_key="sk-fake",
        )

        record = ToolCallRecord(
            tool_name="view_salary",
            tool_args={},
            tool_call_id="tc-003",
        )

        from unittest.mock import patch

        with (
            patch("app.agent.nodes.get_tool", return_value=MockBossTool()),
            patch("app.agent.nodes.tool_circuit_breaker") as mock_cb,
        ):
            mock_cb.allow_request.return_value = True
            result = await _execute_single_tool(record, config)

        assert result.status == "blocked"
        assert "权限" in result.result


# ═══════════════════════════════════════════════════════════════════════════════
#  确认阈值配置测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfirmationThresholds:
    """测试确认阈值配置"""

    def test_high_value_threshold_is_50000(self):
        """高金额阈值应为 50000"""
        assert CONFIRMATION_THRESHOLDS["high_value_amount"] == 50_000

    def test_bulk_threshold_is_5(self):
        """批量操作阈值应为 5"""
        assert CONFIRMATION_THRESHOLDS["bulk_record_count"] == 5

    def test_exactly_at_threshold_blocked(self):
        """金额恰好等于阈值时应被阻止"""
        tool = MockNormalTool()
        result = tool.check_confirmation(
            args={"amount": 50000},
            system_confirmed=False,
        )
        assert result is not None

    def test_just_below_threshold_allowed(self):
        """金额略低于阈值时应允许"""
        tool = MockNormalTool()
        result = tool.check_confirmation(
            args={"amount": 49999},
            system_confirmed=False,
        )
        assert result is None
