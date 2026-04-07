"""Unit tests for _gc_state() — State auto-compression / garbage collection."""


from app.agent.graph import _gc_state
from app.agent.state import ToolCallRecord


def _make_state(**overrides) -> dict:
    """Build a minimal AgentState-like dict for testing."""
    base = {
        "iteration": 0,
        "messages": [],
        "thinking_steps": [],
        "_tool_call_history": [],
        "completed_tool_calls": [],
    }
    base.update(overrides)
    return base


class TestGCState:
    def test_gc_prunes_thinking_steps(self):
        state = _make_state(thinking_steps=[f"step_{i}" for i in range(15)])
        _gc_state(state)
        assert len(state["thinking_steps"]) == 10
        assert state["thinking_steps"][0] == "step_5"

    def test_gc_prunes_tool_call_history(self):
        state = _make_state(_tool_call_history=[{"tool": f"t{i}"} for i in range(10)])
        _gc_state(state)
        assert len(state["_tool_call_history"]) == 5
        assert state["_tool_call_history"][0] == {"tool": "t5"}

    def test_gc_folds_completed_tool_calls(self):
        records = [
            ToolCallRecord(
                tool_name=f"tool_{i}", tool_args={}, tool_call_id=f"id_{i}",
                result=f"result_{i}", status="success",
            )
            for i in range(12)
        ]
        state = _make_state(completed_tool_calls=records)
        _gc_state(state)
        result = state["completed_tool_calls"]
        # 1 summary + 5 recent = 6
        assert len(result) == 6
        assert result[0].tool_name == "_gc_summary"
        assert result[-1].tool_name == "tool_11"

    def test_gc_no_op_when_small(self):
        state = _make_state(
            thinking_steps=["a", "b"],
            _tool_call_history=[{"x": 1}],
            completed_tool_calls=[
                ToolCallRecord(tool_name="t", tool_args={}, tool_call_id="1", result="r", status="success")
            ],
        )
        _gc_state(state)
        assert len(state["thinking_steps"]) == 2
        assert len(state["_tool_call_history"]) == 1
        assert len(state["completed_tool_calls"]) == 1
