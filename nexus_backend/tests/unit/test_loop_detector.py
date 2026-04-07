"""
Loop Detector 单元测试

覆盖：4 种检测策略 + 指纹生成 + 边界条件
"""
from unittest.mock import MagicMock

from app.agent.loop_detector import (
    GENERIC_REPEAT_THRESHOLD,
    GLOBAL_CIRCUIT_BREAKER,
    POLL_NO_PROGRESS_THRESHOLD,
    detect_loop,
    tool_call_fingerprint,
)
from app.agent.state import ToolCallRecord


def _make_tc(name: str, args: dict | None = None):
    """创建用于 fingerprint 测试的 MagicMock（仅需 tool_name/tool_args）"""
    tc = MagicMock()
    tc.tool_name = name
    tc.tool_args = args or {}
    return tc


def _make_record(name: str, args: dict | None = None) -> ToolCallRecord:
    """创建用于 detect_loop 测试的真实 ToolCallRecord"""
    return ToolCallRecord(
        tool_name=name,
        tool_args=args or {},
        tool_call_id=f"tc-{name}",
        result="ok",
        status="success",
    )


class TestToolCallFingerprint:
    def test_empty_list(self):
        assert tool_call_fingerprint([]) == ""

    def test_deterministic(self):
        tc = _make_tc("GetCustomersTool", {"limit": 10})
        fp1 = tool_call_fingerprint([tc])
        fp2 = tool_call_fingerprint([tc])
        assert fp1 == fp2

    def test_different_args_different_fingerprint(self):
        tc1 = _make_tc("GetCustomersTool", {"limit": 10})
        tc2 = _make_tc("GetCustomersTool", {"limit": 20})
        assert tool_call_fingerprint([tc1]) != tool_call_fingerprint([tc2])

    def test_sorted_by_tool_name(self):
        """多工具调用按名称排序，顺序无关"""
        tc_a = _make_tc("A_Tool", {"x": 1})
        tc_b = _make_tc("B_Tool", {"y": 2})
        fp1 = tool_call_fingerprint([tc_a, tc_b])
        fp2 = tool_call_fingerprint([tc_b, tc_a])
        assert fp1 == fp2


class TestDetectLoopGenericRepeat:
    """Detector 1: 同一指纹连续 N 次"""

    def test_no_loop_with_short_history(self):
        state = {"_tool_call_history": ["fp1"], "completed_tool_calls": []}
        assert detect_loop(state) is False

    def test_generic_repeat_detected(self):
        fp = "abc123"
        state = {
            "_tool_call_history": [fp] * GENERIC_REPEAT_THRESHOLD,
            "completed_tool_calls": [],
        }
        assert detect_loop(state) is True

    def test_no_repeat_with_varied_fingerprints(self):
        state = {
            "_tool_call_history": ["fp1", "fp2", "fp3"],
            "completed_tool_calls": [],
        }
        assert detect_loop(state) is False


class TestDetectLoopPingPong:
    """Detector 2: A-B-A-B 交替模式"""

    def test_ping_pong_detected(self):
        state = {
            "_tool_call_history": ["fpA", "fpB", "fpA", "fpB"],
            "completed_tool_calls": [],
        }
        assert detect_loop(state) is True

    def test_no_ping_pong_with_same(self):
        state = {
            "_tool_call_history": ["fpA", "fpA", "fpA", "fpA"],
            "completed_tool_calls": [],
        }
        # 这是 generic repeat，不是 ping-pong（A==B 时不触发）
        assert detect_loop(state) is True  # 被 generic repeat 捕获


class TestDetectLoopPollNoProgress:
    """Detector 3: 轮询工具无进展"""

    def test_poll_tool_exceeds_threshold(self):
        tcs = [_make_record("get_pending_approvals")] * POLL_NO_PROGRESS_THRESHOLD
        state = {
            "_tool_call_history": ["fp"] * 2,
            "completed_tool_calls": tcs,
        }
        assert detect_loop(state) is True

    def test_non_poll_tool_not_flagged(self):
        tcs = [_make_record("GetCustomersTool")] * POLL_NO_PROGRESS_THRESHOLD
        state = {
            "_tool_call_history": ["fp1", "fp2"],
            "completed_tool_calls": tcs,
        }
        assert detect_loop(state) is False


class TestDetectLoopCircuitBreaker:
    """Detector 4: 全局断路器"""

    def test_circuit_breaker_triggered(self):
        tcs = [_make_record("SomeTool")] * GLOBAL_CIRCUIT_BREAKER
        state = {
            "_tool_call_history": ["fp1", "fp2"],
            "completed_tool_calls": tcs,
        }
        assert detect_loop(state) is True

    def test_under_limit_ok(self):
        tcs = [_make_record("SomeTool")] * (GLOBAL_CIRCUIT_BREAKER - 1)
        state = {
            "_tool_call_history": ["fp1", "fp2"],
            "completed_tool_calls": tcs,
        }
        assert detect_loop(state) is False


class TestDetectLoopEdgeCases:
    def test_empty_history(self):
        state = {"_tool_call_history": [], "completed_tool_calls": []}
        assert detect_loop(state) is False

    def test_missing_key(self):
        state = {}
        assert detect_loop(state) is False

    def test_empty_fingerprint_not_counted(self):
        """空指纹不应触发 generic repeat"""
        state = {
            "_tool_call_history": [""] * 10,
            "completed_tool_calls": [],
        }
        assert detect_loop(state) is False
