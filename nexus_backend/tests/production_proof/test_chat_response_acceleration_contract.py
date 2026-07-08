from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def test_chat_response_acceleration_backend_contract():
    service = read("nexus_backend/app/services/chat_response_acceleration_service.py")
    chat_router = read("nexus_backend/app/routers/chat.py")
    chat_service = read("nexus_backend/app/services/chat_service.py")
    unit_tests = read(
        "nexus_backend/tests/unit/test_chat_response_acceleration_service.py"
    )

    for token in [
        "three_layer_chat_path",
        "streaming_first_response",
        "layered_context_injection",
        "parallel_context_load_budget",
        "read_write_tool_execution_tiers",
        "semantic_tool_result_cache",
        "low_cost_model_quality_fallback",
        "prompt_template_and_tool_schema_slimming",
        "conditional_reflect_critic_policy",
        "latency_harness",
    ]:
        assert token in service

    for token in [
        "FastPathDecision",
        "ContextLoadBudget",
        "ToolResultCachePolicy",
        "ConditionalReflectPolicy",
        "ChatLatencyTrace",
        "deepseek-v4-flash",
        "ToolSearch top-k",
        "time_to_first_token",
    ]:
        assert token in service

    assert "stream_fast_path" in chat_router
    assert "agent_path_selected" in chat_router
    assert "semantic_cache_hit" in chat_router
    assert "get_cached_tool_result" in chat_service
    assert "set_cached_tool_result" in chat_service
    assert "test_acceleration_contract_covers_ten_areas" in unit_tests
