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
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.state import AgentConfig, ToolCallRecord
from app.tools.base_tool import BaseTool

# ═══════════════════════════════════════════════════════════════════════════════
#  Helper: 测试用工具
# ═══════════════════════════════════════════════════════════════════════════════


class SlowTool(BaseTool):
    """模拟执行超慢的工具"""

    requires_org_id = False

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

    requires_org_id = False

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

    requires_org_id = False

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

    requires_org_id = False

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
            tool_timeout=1,  # 非常短的超时
        )

        record = ToolCallRecord(
            tool_name="slow_tool",
            tool_args={},
            tool_call_id="tc-timeout-001",
        )

        with (
            patch("app.agent.node_execute.get_tool", return_value=SlowTool()),
            patch("app.agent.node_execute.tool_circuit_breaker") as mock_cb,
            patch("app.agent.loop_detector.record_tool_call_redis", return_value=False),
        ):
            mock_cb.allow_request.return_value = True
            config.user_role = "admin"
            result = await _execute_single_tool(record, config)

        assert result.status == "error"
        # format_friendly_error 将超时信息转为中文友好消息
        assert "超时" in result.result or "重试" in result.result


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
            patch("app.agent.node_execute.get_tool", return_value=ErrorTool()),
            patch("app.agent.node_execute.tool_circuit_breaker") as mock_cb,
            patch("app.agent.node_execute.record_tool_execution"),
            patch("app.agent.loop_detector.record_tool_call_redis", return_value=False),
        ):
            mock_cb.allow_request.return_value = True
            mock_cb.record_failure = lambda: None
            config.user_role = "admin"
            result = await _execute_single_tool(record, config)

        assert result.status == "error"
        # format_friendly_error 输出中文友好消息
        assert "⚠️" in result.result

    async def test_tool_exception_result_contains_error_message(self):
        """异常工具的 result 应包含用户友好的错误信息"""
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
            patch("app.agent.node_execute.get_tool", return_value=ErrorTool()),
            patch("app.agent.node_execute.tool_circuit_breaker") as mock_cb,
            patch("app.agent.node_execute.record_tool_execution"),
            patch("app.agent.loop_detector.record_tool_call_redis", return_value=False),
        ):
            mock_cb.allow_request.return_value = True
            mock_cb.record_failure = lambda: None
            config.user_role = "admin"
            result = await _execute_single_tool(record, config)

        # format_friendly_error 将 RuntimeError("数据库连接失败") 映射为
        # "操作暂时失败，正在为您重试..."（通用可重试错误消息）
        assert "⚠️" in result.result
        assert isinstance(result.result, str) and len(result.result) > 0


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
            patch("app.agent.node_execute.get_tool", return_value=NoneReturnTool()),
            patch("app.agent.node_execute.tool_circuit_breaker") as mock_cb,
            patch("app.agent.node_execute.record_tool_execution"),
            patch("app.agent.loop_detector.record_tool_call_redis", return_value=False),
        ):
            mock_cb.allow_request.return_value = True
            mock_cb.record_success = lambda: None
            config.user_role = "admin"
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

        with patch("app.agent.node_execute.get_tool", return_value=None):
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
            patch("app.agent.node_execute.get_tool", return_value=SuccessTool()),
            patch("app.agent.node_execute.tool_circuit_breaker") as mock_cb,
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

    @pytest.fixture
    def authorized_call(self, monkeypatch):
        config = AgentConfig(
            user_id="user-007",
            user_role="admin",
            org_id="org-007",
            session_id="session-007",
            api_key="sk-fake",
        )
        tool = SuccessTool()
        tool.requires_org_id = True
        tool.run = AsyncMock(return_value="查询结果")
        monkeypatch.setattr("app.agent.node_execute.get_tool", lambda _: tool)
        monkeypatch.setattr(
            "app.agent.node_execute.tool_circuit_breaker.allow_request", lambda: True
        )
        monkeypatch.setattr(
            "app.agent.node_execute.record_tool_execution", lambda *_: None
        )
        monkeypatch.setattr("app.agent.node_execute.check_tool_alert", lambda *_: None)
        monkeypatch.setattr(
            "app.agent.loop_detector.record_tool_call_redis",
            AsyncMock(return_value=False),
        )
        monkeypatch.setattr(
            "app.agent.node_execute.check_symbolic_policy",
            AsyncMock(return_value=SimpleNamespace(allowed=True)),
        )

        async def passthrough(_event, context):
            return context

        monkeypatch.setattr("app.agent.node_execute.run_hooks", passthrough)
        return config, tool, {}

    @staticmethod
    async def execute(config, cache, query="test"):
        from app.agent.nodes import _execute_single_tool

        return await _execute_single_tool(
            ToolCallRecord(
                tool_name="success_tool",
                tool_args={"query": query},
                tool_call_id="tc-idem-001",
            ),
            config,
            cache,
        )

    async def test_cached_result_returned(self, authorized_call):
        """通过真实执行填充缓存，同一授权上下文不重复调用工具。"""
        config, tool, cache = authorized_call
        first = await self.execute(config, cache)
        second = await self.execute(config, cache)
        assert first.status == second.status == "success"
        assert first.result == second.result == "查询结果"
        assert first.duration_ms == second.duration_ms
        tool.run.assert_awaited_once()

    @pytest.mark.parametrize(
        "field,value",
        [
            ("org_id", "org-other"),
            ("user_id", "user-other"),
            ("user_role", "boss"),
            ("session_id", "session-other"),
            ("token", "new-token"),
        ],
    )
    async def test_cache_isolated_by_actor_context(self, authorized_call, field, value):
        config, tool, cache = authorized_call
        assert (await self.execute(config, cache)).status == "success"
        changed = config.model_copy(update={field: value})
        assert (await self.execute(changed, cache)).status == "success"
        assert tool.run.await_count == 2

    async def test_changed_arguments_do_not_reuse_cache(self, authorized_call):
        config, tool, cache = authorized_call
        await self.execute(config, cache)
        assert (
            await self.execute(config, cache, query="different")
        ).status == "success"
        assert tool.run.await_count == 2

    @pytest.mark.parametrize("change", [{"org_id": None}, {"user_role": "employee"}])
    async def test_cache_never_bypasses_current_authorization(
        self, authorized_call, change
    ):
        config, tool, cache = authorized_call
        assert (await self.execute(config, cache)).status == "success"
        result = await self.execute(config.model_copy(update=change), cache)
        assert result.status == "blocked"
        assert result.result != "查询结果"
        tool.run.assert_awaited_once()

    async def test_legacy_unscoped_cache_is_not_trusted(self, authorized_call):
        config, tool, cache = authorized_call
        cache["tc-idem-001:success_tool"] = {"status": "success", "result": "旧缓存"}
        result = await self.execute(config, cache)
        assert result.result == "查询结果"
        tool.run.assert_awaited_once()


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
            gather_timeout=1,  # 极短超时
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
        async def slow_execute(
            record, config, cache=None, prior_completed=None, trace_id=None
        ):
            await asyncio.sleep(100)
            return record

        with (
            patch(
                "app.agent.node_execute._execute_single_tool", side_effect=slow_execute
            ),
            patch(
                "app.agent.node_execute.plugin_system_service.run_hooks",
                new_callable=AsyncMock,
            ),
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

        with patch(
            "app.agent.node_respond.plugin_system_service.run_hooks",
            new_callable=AsyncMock,
        ):
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

        with patch(
            "app.agent.node_respond.plugin_system_service.run_hooks",
            new_callable=AsyncMock,
        ):
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

        with patch(
            "app.agent.node_respond.plugin_system_service.run_hooks",
            new_callable=AsyncMock,
        ):
            result = await error_node(state)

        assert result["current_phase"] == AgentPhase.RESPONDING
        assert "final_response" in result


# 导入 AgentPhase 供 error_node 测试使用
from app.agent.state import AgentPhase
