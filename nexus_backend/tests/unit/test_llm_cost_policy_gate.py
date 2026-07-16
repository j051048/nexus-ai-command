from app.agent.state import AgentConfig, QueryComplexity
from app.services.agent_operational_hardening import (
    LOW_COST_DEFAULT_MODEL,
    enforce_model_policy,
)
from app.services.llm_gateway.model_resolution import _apply_cost_policy


def test_scheduled_tasks_cannot_select_expensive_model_in_production():
    decision = enforce_model_policy(
        "gemini-3.1-pro-preview",
        source="scheduled_task",
        environment="production",
    )
    assert decision.allowed is False
    assert decision.resolved_model == LOW_COST_DEFAULT_MODEL


def test_gateway_cost_policy_overrides_database_schedule_rule():
    assert (
        _apply_cost_policy("gemini-3-flash-preview", "scheduled_task", "schedule_rule")
        == LOW_COST_DEFAULT_MODEL
    )


def test_complex_agent_tasks_never_upgrade_to_expensive_model():
    config = AgentConfig(
        user_id="user-1",
        model="gemini-3.1-pro-preview",
        mini_model="gemini-3-flash-preview",
        resolved_configs={
            "flagship": {
                "model": "gemini-3.1-pro-preview",
                "temperature": 0.2,
                "supports_tools": True,
            }
        },
    )

    assert (
        config.get_model_for_complexity(QueryComplexity.CRITICAL)
        == LOW_COST_DEFAULT_MODEL
    )
    assert (
        config.get_tier_config(QueryComplexity.CRITICAL)["model"]
        == LOW_COST_DEFAULT_MODEL
    )
