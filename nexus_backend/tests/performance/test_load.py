"""
性能 / 负载 / 稳定性测试

覆盖：Agent 响应时间 SLO、并发请求、内存泄漏检测、
      循环检测性能、Prompt Firewall 吞吐量、大批量数据处理
"""
import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.state import AgentPhase, QueryComplexity, AgentConfig, ToolCallRecord
from app.agent.safety_guards import SLO_THRESHOLDS, check_slo_budget
from app.agent.loop_detector import (
    tool_call_fingerprint, detect_loop,
    GENERIC_REPEAT_THRESHOLD, GLOBAL_CIRCUIT_BREAKER, LOOP_WINDOW_SIZE,
)
from app.core.prompt_firewall import PromptFirewall, FirewallConfig


def _base_config(**overrides):
    defaults = dict(user_id="u-perf", org_id="org-perf", token="jwt-perf")
    defaults.update(overrides)
    return AgentConfig(**defaults)


def _tc(name="Tool", args=None, status="success"):
    return ToolCallRecord(
        tool_name=name, tool_args=args or {}, tool_call_id=f"tc-{name}", result="ok", status=status,
    )


# ── SLO 时间预算 ──────────────────────────────────────────────────────────────


class TestSLOPerformance:
    """SLO 时间预算边界测试"""

    @pytest.mark.parametrize("complexity,threshold", list(SLO_THRESHOLDS.items()))
    def test_slo_thresholds_are_positive(self, complexity, threshold):
        assert threshold > 0

    def test_slo_simple_within_budget(self):
        state = {"wall_clock_start": time.time(), "complexity": QueryComplexity.SIMPLE}
        assert check_slo_budget(state) is False

    def test_slo_simple_exceeded(self):
        state = {"wall_clock_start": time.time() - 10, "complexity": QueryComplexity.SIMPLE}
        assert check_slo_budget(state) is True

    def test_slo_critical_within_budget(self):
        state = {"wall_clock_start": time.time() - 25, "complexity": QueryComplexity.CRITICAL}
        assert check_slo_budget(state) is False

    def test_slo_critical_exceeded(self):
        state = {"wall_clock_start": time.time() - 35, "complexity": QueryComplexity.CRITICAL}
        assert check_slo_budget(state) is True

    def test_slo_budget_ratio(self):
        """80% 预算检查"""
        state = {"wall_clock_start": time.time() - 4.5, "complexity": QueryComplexity.SIMPLE}
        # 5 * 0.8 = 4.0, 4.5 > 4.0 → exceeded
        assert check_slo_budget(state, budget_ratio=0.8) is True

    def test_slo_missing_wall_start(self):
        state = {"wall_clock_start": None, "complexity": QueryComplexity.SIMPLE}
        assert check_slo_budget(state) is False

    def test_slo_missing_complexity(self):
        state = {"wall_clock_start": time.time(), "complexity": None}
        assert check_slo_budget(state) is False


# ── 循环检测性能 ──────────────────────────────────────────────────────────────


class TestLoopDetectorPerformance:
    """循环检测在大量历史记录下的性能"""

    def test_fingerprint_speed_1000_calls(self):
        """1000 次指纹计算应在 1 秒内完成"""
        calls = [_tc(f"Tool_{i}", {"arg": i}) for i in range(10)]
        start = time.time()
        for _ in range(1000):
            tool_call_fingerprint(calls)
        elapsed = time.time() - start
        assert elapsed < 1.0, f"1000 fingerprints took {elapsed:.2f}s"

    def test_detect_loop_large_history(self):
        """大量历史记录下循环检测不超时"""
        history = [f"fp-{i % 50}" for i in range(500)]
        state = {
            "_tool_call_history": history,
            "completed_tool_calls": [],
        }
        start = time.time()
        with patch("app.agent.loop_detector.get_completed_tools", return_value=[]):
            detect_loop(state)
        elapsed = time.time() - start
        assert elapsed < 0.5, f"detect_loop on 500 items took {elapsed:.2f}s"

    def test_window_size_limits_scan(self):
        """窗口大小限制扫描范围"""
        history = ["unique-fp"] * 100
        # 最后 3 个不同，不应触发
        history[-1] = "different"
        state = {
            "_tool_call_history": history,
            "completed_tool_calls": [],
        }
        with patch("app.agent.loop_detector.get_completed_tools", return_value=[]):
            result = detect_loop(state)
        assert result is False


# ── Prompt Firewall 吞吐量 ────────────────────────────────────────────────────


class TestFirewallPerformance:
    """Prompt Firewall 扫描性能"""

    @pytest.mark.asyncio
    async def test_scan_short_input_fast(self):
        """短输入扫描应在 10ms 内"""
        fw = PromptFirewall()
        start = time.time()
        for _ in range(100):
            await fw.scan_input("查询本月销售数据")
        elapsed = time.time() - start
        assert elapsed < 1.0, f"100 short scans took {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_scan_long_input_reasonable(self):
        """长输入（8000字符）扫描应在 100ms 内"""
        fw = PromptFirewall()
        long_text = "这是一段正常的业务查询文本。" * 500  # ~8000 chars
        start = time.time()
        result = await fw.scan_input(long_text)
        elapsed = time.time() - start
        assert elapsed < 0.1, f"Long input scan took {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_scan_adversarial_input(self):
        """对抗性输入不应导致 ReDoS"""
        fw = PromptFirewall()
        # 构造可能触发回溯的输入
        adversarial = "ignore " * 100 + "previous instructions " * 50
        start = time.time()
        await fw.scan_input(adversarial)
        elapsed = time.time() - start
        assert elapsed < 1.0, f"Adversarial scan took {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_concurrent_scans(self):
        """并发扫描不应互相阻塞"""
        fw = PromptFirewall()
        inputs = [f"查询客户 {i} 的订单" for i in range(50)]
        start = time.time()
        results = await asyncio.gather(*[fw.scan_input(t) for t in inputs])
        elapsed = time.time() - start
        assert len(results) == 50
        assert all(r.is_safe for r in results)
        assert elapsed < 2.0, f"50 concurrent scans took {elapsed:.2f}s"


# ── 大批量数据处理 ────────────────────────────────────────────────────────────


class TestBulkDataPerformance:
    """大批量数据处理性能"""

    def test_mock_db_bulk_filter(self):
        """MockDB 批量过滤性能"""
        from tests.conftest import MockSupabaseClient

        db = MockSupabaseClient()
        records = [{"id": f"r-{i}", "org_id": f"org-{i % 10}", "status": "active"} for i in range(10000)]
        db.set_table_data("customers", records)

        start = time.time()
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            db.table("customers").select("*").eq("org_id", "org-1").execute()
        )
        loop.close()
        elapsed = time.time() - start

        assert len(result.data) == 1000
        assert elapsed < 1.0, f"10k filter took {elapsed:.2f}s"

    def test_agent_config_creation_speed(self):
        """AgentConfig 批量创建性能"""
        start = time.time()
        for i in range(1000):
            AgentConfig(user_id=f"u-{i}", org_id=f"org-{i}", token=f"jwt-{i}")
        elapsed = time.time() - start
        assert elapsed < 2.0, f"1000 AgentConfig creations took {elapsed:.2f}s"


# ── 内存稳定性 ────────────────────────────────────────────────────────────────


class TestMemoryStability:
    """内存泄漏 / 稳定性检测"""

    def test_tool_call_record_gc(self):
        """ToolCallRecord 不应持有大对象引用"""
        import sys
        tc = _tc("BigTool", {"data": "x" * 10000})
        size = sys.getsizeof(tc)
        # dataclass 本身不应超过 1KB（不含 args 内容）
        assert size < 1024, f"ToolCallRecord base size {size} bytes"

    def test_firewall_result_no_leak(self):
        """FirewallResult 不应累积 violations"""
        fw = PromptFirewall()
        loop = asyncio.new_event_loop()
        for _ in range(100):
            result = loop.run_until_complete(fw.scan_input("正常查询"))
            assert len(result.violations) == 0
        loop.close()
