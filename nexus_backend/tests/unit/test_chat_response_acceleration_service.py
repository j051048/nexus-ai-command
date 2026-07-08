import asyncio

from app.services.chat_response_acceleration_service import (
    ChatLatencyTrace,
    ContextLoadBudget,
    chat_response_acceleration_service,
)


class _ReadTool:
    is_irreversible = False


class _WriteTool:
    is_irreversible = True


def test_fast_path_bypasses_llm_for_safe_greeting():
    decision = chat_response_acceleration_service.classify_chat_path(
        message="你好",
        agent=None,
    )

    assert decision.path == "fast_path"
    assert decision.can_answer is True
    assert decision.bypasses_llm is True


def test_business_query_keeps_deep_agent_quality_path():
    decision = chat_response_acceleration_service.classify_chat_path(
        message="帮我分析 30 天未跟进客户并生成跟进计划",
        agent="crm",
    )

    assert decision.path == "deep_agent_path"
    assert decision.can_answer is False


def test_context_load_budget_defers_slow_context():
    async def _fast():
        return "ok"

    async def _slow():
        await asyncio.sleep(0.05)
        return "late"

    result = asyncio.run(
        chat_response_acceleration_service.run_budgeted_context_loaders(
            {"fast": _fast, "slow": _slow},
            budget=ContextLoadBudget(timeout_ms=5),
        )
    )

    assert result["loaded"]["fast"] == "ok"
    assert "slow" in result["deferred"]


def test_tool_result_cache_policy_allows_only_safe_read_tools():
    read_policy = chat_response_acceleration_service.build_tool_result_cache_policy(
        tool_name="query_customers",
        args={"stage": "stale"},
        user_id="user-1",
        org_id="org-1",
        user_role="sales",
        tool=_ReadTool(),
    )
    write_policy = chat_response_acceleration_service.build_tool_result_cache_policy(
        tool_name="approve_expense",
        args={"id": "approval-1"},
        user_id="user-1",
        org_id="org-1",
        user_role="boss",
        tool=_WriteTool(),
    )

    assert read_policy.cacheable is True
    assert read_policy.tier == "read_parallel"
    assert write_policy.cacheable is False
    assert write_policy.tier == "write_serial_hitl"


def test_conditional_reflect_policy_preserves_quality_for_high_risk_tools():
    high_risk = chat_response_acceleration_service.build_conditional_reflect_policy(
        complexity="complex",
        has_write_or_high_risk_tool=True,
    )
    low_confidence = (
        chat_response_acceleration_service.build_conditional_reflect_policy(
            complexity="moderate",
            confidence_score=0.5,
        )
    )
    slo_guard = chat_response_acceleration_service.build_conditional_reflect_policy(
        complexity="moderate",
        confidence_score=0.95,
        elapsed_ms=6000,
    )

    assert high_risk.decision == "reflect_and_critic"
    assert high_risk.requires_critic is True
    assert low_confidence.decision == "reflect"
    assert slo_guard.decision == "skip"


def test_model_quality_policy_forces_low_cost_default():
    policy = chat_response_acceleration_service.build_model_quality_policy(
        "gemini-3.1-pro-preview"
    )

    assert policy["default_model"] == "deepseek-v4-flash"
    assert policy["model_policy_decision"]["resolved_model"] == "deepseek-v4-flash"


def test_prompt_slimming_limits_tool_schema_count():
    plan = chat_response_acceleration_service.build_prompt_and_tool_slimming_plan(
        tool_count=100,
        path="deep_agent_path",
    )

    assert plan["tool_schema_strategy"] == "ToolSearch top-k before prompt injection"
    assert plan["tool_schema_limit"] <= 8


def test_latency_trace_records_stage_marks():
    trace = ChatLatencyTrace(trace_id="trace-1")
    trace.mark("intent_route")
    payload = trace.to_dict()

    assert payload["trace_id"] == "trace-1"
    assert "intent_route" in payload["marks_ms"]


def test_acceleration_contract_covers_ten_areas():
    contract = chat_response_acceleration_service.get_acceleration_contract()
    validation = chat_response_acceleration_service.validate_acceleration_contract()

    assert len(contract["areas"]) == 10
    assert validation["passed"] is True
    assert validation["area_count"] == 10
