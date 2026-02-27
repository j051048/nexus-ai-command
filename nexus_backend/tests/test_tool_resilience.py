"""
#8 — Tool Resilience (工具超时与重试测试)

测试错误处理:
- 工具执行超时 -> 捕获并记录错误
- 工具抛出异常 -> status 设为 "error", result 包含错误信息
- 工具返回 None -> 优雅处理
- 工具不存在 -> 返回 "not found" 错误
- 断路器打开 -> 立即返回错误
- 幂等性: 相同 tool_call_id 不重复执行
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.state import AgentConfig, ToolCallRecord
from app.tools.base_tool import BaseTool


# ═══════════════════════════════════════════════════════════════════════════════
#  Helper: 测试用工具
# ═══════════════════════════════════════════════════════════════════════════════


class SlowTool(BaseTool):
    """模拟执行超慢的工具"""

    @property
    def name(self) -> str:
        return "slow_tool"

    @property
    def description(self) -> str:
        return "一个很慢的工具"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def run(self, args, user_id, config=None):
        await asyncio.sleep(100)  # 模拟超长执行
        return "不应该到达这里"


class ErrorTool(BaseTool):
    """模拟抛出异常的工具"""

    @property
    def name(self) -> str:
        return "error_tool"

    @property
    def description(self) -> str:
        return "一个会报错的工具"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def run(self, args, user_id, config=None):
        raise RuntimeError("数据库连接失败")


class NoneReturnTool(BaseTool):
    """模拟返回 None 的工具"""

    @property
    def name(self) -> str:
        return "none_tool"

    @property
    def description(self) -> str:
        return "返回 None 的工具"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def run(self, args, user_id, config=None):
        return None


class SuccessTool(BaseTool):
    """模拟正常执行的工具"""

    @property
    def name(self) -> str:
        return "success_tool"

    @property
    def description(self) -> str:
        return "正常工具"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {"query": {"type": "string"}}}

    async def run(self, args, user_id, config=None):
        return f"查询结果: {args.get('query', '')}"


# ═══════════════════════════════════════════════════════════════════════════════
#  工具超时测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestToolTimeout:
    """测试工具执行超时处理"""

    async def test_tool_timeout_caught(self):
        """工具超时应被捕获并标记为 error"""
        from app.agent.nodes import _execute_single_tool

        config = AgentConfig(
            user_id="user-001",
            api_key="sk-fake",
            tool_timeout=0.1,  # 非常短的超时
        )

        record = ToolCallRecord(
            tool_name="slow_tool",
            tool_args={},
            tool_call_id="tc-timeout-001",
        )

        with (
            patch("app.agent.nodes.get_tool", return_value=SlowTool()),
            patch("app.agent.nodes.tool_circuit_breaker") as mock_cb,
        ):
            mock_cb.allow_request.return_value = True
            result = await _execute_single_tool(record, config)

        assert result.status == "error"
        assert "timed out" in result.result.lower() or "timeout" in result.result.lower()


# ═══════════════════════════════════════════════════════════════════════════════
#  工具异常测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestToolException:
    """测试工具执行异常处理"""

    async def test_tool_exception_sets_error_status(self):
        """工具抛出异常应将 status 设为 error"""
        from app.agent.nodes import _execute_single_tool

        config = AgentConfig(
            user_id="user-002",
            api_key="sk-fake",
            tool_timeout=5,
        )

        record = ToolCallRecord(
            tool_name="error_tool",
            tool_args={},
            tool_call_id="tc-error-001",
        )

        with (
            patch("app.agent.nodes.get_tool", return_value=ErrorTool()),
            patch("app.agent.nodes.tool_circuit_breaker") as mock_cb,
            patch("app.agent.nodes.record_tool_execution"),
        ):
            mock_cb.allow_request.return_value = True
            mock_cb.record_failure = lambda: None
            result = await _execute_single_tool(record, config)

        assert result.status == "error"
        assert "failed" in result.result.lower() or "失败" in result.result

    async def test_tool_exception_result_contains_error_message(self):
        """异常工具的 result 应包含错误信息"""
        from app.agent.nodes import _execute_single_tool

        config = AgentConfig(
            user_id="user-003",
            api_key="sk-fake",
            tool_timeout=5,
        )

        record = ToolCallRecord(
            tool_name="error_tool",
            tool_args={},
            tool_call_id="tc-error-002",
        )

        with (
            patch("app.agent.nodes.get_tool", return_value=ErrorTool()),
            patch("app.agent.nodes.tool_circuit_breaker") as mock_cb,
            patch("app.agent.nodes.record_tool_execution"),
        ):
            mock_cb.allow_request.return_value = True
            mock_cb.record_failure = lambda: None
            result = await _execute_single_tool(record, config)

        assert "数据库连接失败" in result.result


# ═══════════════════════════════════════════════════════════════════════════════
#  工具返回 None 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestToolNoneReturn:
    """测试工具返回 None 的处理"""

    async def test_none_return_handled_gracefully(self):
        """工具返回 None 应被优雅处理"""
        from app.agent.nodes import _execute_single_tool

        config = AgentConfig(
            user_id="user-004",
            api_key="sk-fake",
            tool_timeout=5,
        )

        record = ToolCallRecord(
            tool_name="none_tool",
            tool_args={},
            tool_call_id="tc-none-001",
        )

        with (
            patch("app.agent.nodes.get_tool", return_value=NoneReturnTool()),
            patch("app.agent.nodes.tool_circuit_breaker") as mock_cb,
            patch("app.agent.nodes.record_tool_execution"),
        ):
            mock_cb.allow_request.return_value = True
            mock_cb.record_success = lambda: None
            result = await _execute_single_tool(record, config)

        assert result.status == "success"
        assert result.result is not None  # str(None) = "None"


# ═══════════════════════════════════════════════════════════════════════════════
#  工具不存在测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestToolNotFound:
    """测试不存在的工具"""

    async def test_unknown_tool_returns_error(self):
        """不存在的工具应返回 error"""
        from app.agent.nodes import _execute_single_tool

        config = AgentConfig(
            user_id="user-005",
            api_key="sk-fake",
        )

        record = ToolCallRecord(
            tool_name="nonexistent_tool",
            tool_args={},
            tool_call_id="tc-404-001",
        )

        with patch("app.agent.nodes.get_tool", return_value=None):
            result = await _execute_single_tool(record, config)

        assert result.status == "error"
        assert "not found" in result.result.lower()


# ═══════════════════════════════════════════════════════════════════════════════
#  断路器测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestCircuitBreaker:
    """测试断路器打开时的行为"""

    async def test_circuit_breaker_open_blocks_tool(self):
        """断路器打开时应立即阻止工具执行"""
        from app.agent.nodes import _execute_single_tool

        config = AgentConfig(
            user_id="user-006",
            api_key="sk-fake",
        )

        record = ToolCallRecord(
            tool_name="any_tool",
            tool_args={},
            tool_call_id="tc-cb-001",
        )

        with (
            patch("app.agent.nodes.get_tool", return_value=SuccessTool()),
            patch("app.agent.nodes.tool_circuit_breaker") as mock_cb,
        ):
            mock_cb.allow_request.return_value = False  # 断路器打开
            result = await _execute_single_tool(record, config)

        assert result.status == "error"
        assert "断路器" in result.result


# ═══════════════════════════════════════════════════════════════════════════════
#  幂等性测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestIdempotency:
    """测试工具执行的幂等性"""

    async def test_cached_result_returned(self):
        """已缓存的 tool_call_id 应直接返回缓存结果"""
        from app.agent.nodes import _execute_single_tool

        config = AgentConfig(
            user_id="user-007",
            api_key="sk-fake",
        )

        record = ToolCallRecord(
            tool_name="success_tool",
            tool_args={"query": "test"},
            tool_call_id="tc-idem-001",
        )

        # 预填充幂等性缓存
        cache = {
            "tc-idem-001:success_tool": {
                "status": "success",
                "result": "缓存的结果",
                "duration_ms": 50,
            }
        }

        with (
            patch("app.agent.nodes.get_tool", return_value=SuccessTool()),
            patch("app.agent.nodes.tool_circuit_breaker") as mock_cb,
        ):
            mock_cb.allow_request.return_value = True
            result = await _execute_single_tool(record, config, cache)

        assert result.status == "success"
        assert result.result == "缓存的结果"
        assert result.duration_ms == 50


# ═══════════════════════════════════════════════════════════════════════════════
#  Execute Node 整体超时测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecuteNodeTimeout:
    """测试 execute_node 的整体超时"""

    async def test_gather_timeout_sets_error_phase(self):
        """工具执行整体超时应设置 ERROR 阶段"""
        from app.agent.nodes import execute_node

        config = AgentConfig(
            user_id="user-008",
            api_key="sk-fake",
            gather_timeout=0.01,  # 极短超时
        )

        pending = [
            ToolCallRecord(
                tool_name="slow_tool",
                tool_args={},
                tool_call_id="tc-gather-001",
            )
        ]

        state = {
            "config": config,
            "pending_tool_calls": pending,
            "completed_tool_calls": [],
            "iteration": 0,
        }

        # 模拟一个慢工具
        async def slow_execute(record, config, cache=None):
            await asyncio.sleep(100)
            return record

        with (
            patch("app.agent.nodes._execute_single_tool", side_effect=slow_execute),
            patch("app.agent.nodes.plugin_system_service.run_hooks", new_callable=AsyncMock),
        ):
            result = await execute_node(state)

        assert result["current_phase"].value == "error"
        assert "超时" in result.get("error", "")


# ═══════════════════════════════════════════════════════════════════════════════
#  Error Node 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorNode:
    """测试错误恢复节点"""

    async def test_level_0_recovery(self):
        """Level 0 错误应尝试 L1 恢复"""
        from app.agent.nodes import error_node

        config = AgentConfig(user_id="user-009", api_key="sk-fake")

        state = {
            "config": config,
            "error": "工具执行失败",
            "error_recovery_level": 0,
            "iteration": 1,
        }

        with patch("app.agent.nodes.plugin_system_service.run_hooks", new_callable=AsyncMock):
            result = await error_node(state)

        assert result["error_recovery_level"] == 1
        assert result["current_phase"] == AgentPhase.PLANNING

    async def test_level_1_recovery(self):
        """Level 1 错误应尝试 L2 恢复（禁用工具）"""
        from app.agent.nodes import error_node

        config = AgentConfig(user_id="user-010", api_key="sk-fake")

        state = {
            "config": config,
            "error": "持续失败",
            "error_recovery_level": 1,
            "iteration": 2,
        }

        with patch("app.agent.nodes.plugin_system_service.run_hooks", new_callable=AsyncMock):
            result = await error_node(state)

        assert result["error_recovery_level"] == 2
        assert result["requires_tools"] is False

    async def test_level_2_gives_up(self):
        """Level 2+ 应放弃恢复并给出友好提示"""
        from app.agent.nodes import error_node

        config = AgentConfig(user_id="user-011", api_key="sk-fake")

        state = {
            "config": config,
            "error": "不可恢复的错误",
            "error_recovery_level": 2,
            "iteration": 4,
        }

        with patch("app.agent.nodes.plugin_system_service.run_hooks", new_callable=AsyncMock):
            result = await error_node(state)

        assert result["current_phase"] == AgentPhase.RESPONDING
        assert "final_response" in result


# 导入 AgentPhase 供 error_node 测试使用
from app.agent.state import AgentPhase
