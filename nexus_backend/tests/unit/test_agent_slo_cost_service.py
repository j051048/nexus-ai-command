from __future__ import annotations

from app.services.agent_slo_cost_service import (
    AgentSLOTargets,
    summarize_agent_slo_cost,
)


def test_agent_slo_cost_summary_is_healthy_for_low_cost_fast_runs():
    result = summarize_agent_slo_cost(
        agent_runs=[
            {"status": "success", "duration_ms": 1200},
            {"status": "completed", "duration_ms": 1800},
        ],
        llm_calls=[
            {
                "model_code": "deepseek-v4-flash",
                "total_tokens": 800,
                "call_cost": 0.001,
                "exec_time_ms": 900,
            }
        ],
    )

    assert result["status"] == "healthy"
    assert result["metrics"]["agent_success_rate"] == 1
    assert result["metrics"]["expensive_model_share"] == 0
    assert result["model_mix"][0]["model_code"] == "deepseek-v4-flash"


def test_agent_slo_cost_summary_flags_expensive_model_and_latency_regression():
    result = summarize_agent_slo_cost(
        agent_runs=[
            {"status": "failed", "duration_ms": 12000},
            {"status": "success", "duration_ms": 9000},
        ],
        llm_calls=[
            {
                "model_code": "gemini-3.1-pro-preview",
                "input_tokens": 1000,
                "output_tokens": 400,
                "call_cost": 0.45,
                "exec_time_ms": 9000,
            }
        ],
        targets=AgentSLOTargets(
            agent_success_rate_min=0.99,
            agent_p95_duration_ms_max=8000,
            llm_p95_latency_ms_max=5000,
            expensive_model_share_max=0.01,
            daily_cost_usd_max=0.1,
        ),
    )

    assert result["status"] == "breaching"
    assert "agent_success_rate_below_slo" in result["violations"]
    assert "agent_p95_duration_above_slo" in result["violations"]
    assert "llm_p95_latency_above_slo" in result["violations"]
    assert "expensive_model_share_above_budget" in result["violations"]
    assert "daily_cost_above_budget" in result["violations"]

