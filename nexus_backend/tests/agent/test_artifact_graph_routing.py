from app.agent.graph import _after_critic, _after_router, _check_fast_synthesis
from app.agent.state import AgentConfig, QueryComplexity, ToolCallRecord

STRICT_SPEC = {
    "artifact_type": "customer_solution",
    "external_delivery": True,
    "strict_quality": True,
    "max_repair_cycles": 2,
}


def test_strict_artifact_never_uses_simple_or_fast_synthesis_path():
    router_state = {
        "complexity": QueryComplexity.SIMPLE,
        "artifact_spec": STRICT_SPEC,
        "intent_summary": "生成客户方案",
    }
    tool_state = {
        "complexity": QueryComplexity.COMPLEX,
        "artifact_spec": STRICT_SPEC,
        "completed_tool_calls": [
            ToolCallRecord(
                tool_name="search_knowledge",
                tool_args={},
                tool_call_id="tool-1",
                status="success",
            )
        ],
    }

    assert _after_router(router_state) != "simple_respond"
    assert _check_fast_synthesis(tool_state) == "reflect"


def test_critic_failure_replans_even_when_execution_policy_exists():
    state = {
        "critic_passed": False,
        "iteration": 1,
        "artifact_repair_count": 1,
        "artifact_spec": STRICT_SPEC,
        "execution_policy": {"max_iterations": 4},
        "config": AgentConfig(user_id="user-1", org_id="org-1"),
    }

    assert _after_critic(state) == "plan"

    state["artifact_repair_count"] = 3
    assert _after_critic(state) == "respond"
    assert state["circuit_break_reason"] == "critic_best_available"
