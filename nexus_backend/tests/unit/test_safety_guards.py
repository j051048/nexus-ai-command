"""
Safety Guards 单元测试

覆盖：不可逆工具检测、mutation fast-path、SLO 预算检查
"""
import time
import pytest
from unittest.mock import MagicMock, patch
from app.agent.safety_guards import (
    has_irreversible_tool,
    is_mutation_fast_path,
    check_slo_budget,
    SLO_THRESHOLDS,
)
from app.agent.state import QueryComplexity


def _make_tc(name: str, status: str = "success", irreversible: bool = False):
    tc = MagicMock()
    tc.tool_name = name
    tc.status = status

    mock_tool = MagicMock()
    mock_tool.is_irreversible = irreversible
    return tc, mock_tool


class TestHasIrreversibleTool:
    @patch("app.agent.safety_guards.get_tool")
    def test_detects_irreversible(self, mock_get_tool):
        tc, tool = _make_tc("ApprovalTool", irreversible=True)
        mock_get_tool.return_value = tool
        state = {"completed_tool_calls": [tc]}
        assert has_irreversible_tool(state) is True

    @patch("app.agent.safety_guards.get_tool")
    def test_no_irreversible(self, mock_get_tool):
        tc, tool = _make_tc("GetCustomersTool", irreversible=False)
        mock_get_tool.return_value = tool
        state = {"completed_tool_calls": [tc]}
        assert has_irreversible_tool(state) is False

    def test_empty_completed(self):
        assert has_irreversible_tool({"completed_tool_calls": []}) is False

    @patch("app.agent.safety_guards.get_tool")
    def test_unknown_tool_returns_none(self, mock_get_tool):
        tc = MagicMock()
        tc.tool_name = "NonExistentTool"
        mock_get_tool.return_value = None
        state = {"completed_tool_calls": [tc]}
        assert has_irreversible_tool(state) is False


class TestIsMutationFastPath:
    @patch("app.agent.safety_guards.get_tool")
    def test_all_success_non_irreversible(self, mock_get_tool):
        tc, tool = _make_tc("CreateCustomerTool", status="success", irreversible=False)
        mock_get_tool.return_value = tool
        state = {"completed_tool_calls": [tc]}
        assert is_mutation_fast_path(state) is True

    @patch("app.agent.safety_guards.get_tool")
    def test_irreversible_blocks_fast_path(self, mock_get_tool):
        tc, tool = _make_tc("ApprovalTool", status="success", irreversible=True)
        mock_get_tool.return_value = tool
        state = {"completed_tool_calls": [tc]}
        assert is_mutation_fast_path(state) is False

    @patch("app.agent.safety_guards.get_tool")
    def test_failed_tool_blocks_fast_path(self, mock_get_tool):
        tc, tool = _make_tc("SomeTool", status="error", irreversible=False)
        mock_get_tool.return_value = tool
        state = {"completed_tool_calls": [tc]}
        assert is_mutation_fast_path(state) is False

    def test_empty_completed_no_fast_path(self):
        assert is_mutation_fast_path({"completed_tool_calls": []}) is False


class TestCheckSloBudget:
    def test_within_budget(self):
        state = {
            "wall_clock_start": time.time() - 1.0,
            "complexity": QueryComplexity.SIMPLE,
        }
        assert check_slo_budget(state) is False

    def test_exceeded_budget(self):
        state = {
            "wall_clock_start": time.time() - 100.0,
            "complexity": QueryComplexity.SIMPLE,
        }
        assert check_slo_budget(state) is True

    def test_no_wall_clock_returns_false(self):
        state = {"complexity": QueryComplexity.SIMPLE}
        assert check_slo_budget(state) is False

    def test_no_complexity_returns_false(self):
        state = {"wall_clock_start": time.time()}
        assert check_slo_budget(state) is False

    def test_budget_ratio(self):
        """80% 预算检查"""
        threshold = SLO_THRESHOLDS[QueryComplexity.MODERATE]
        state = {
            "wall_clock_start": time.time() - (threshold * 0.85),
            "complexity": QueryComplexity.MODERATE,
        }
        # 85% elapsed > 80% budget → exceeded
        assert check_slo_budget(state, budget_ratio=0.8) is True

    @pytest.mark.parametrize("complexity,threshold", [
        (QueryComplexity.SIMPLE, 5.0),
        (QueryComplexity.MODERATE, 10.0),
        (QueryComplexity.COMPLEX, 20.0),
        (QueryComplexity.CRITICAL, 30.0),
    ])
    def test_slo_thresholds_correct(self, complexity, threshold):
        assert SLO_THRESHOLDS[complexity] == threshold
