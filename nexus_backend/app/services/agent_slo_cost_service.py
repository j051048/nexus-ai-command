"""Agent SLO and LLM cost summary helpers."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

EXPENSIVE_MODEL_MARKERS = (
    "gemini",
    "gpt-4",
    "gpt-5",
    "claude-opus",
    "claude-4",
)


@dataclass(frozen=True)
class AgentSLOTargets:
    agent_success_rate_min: float = 0.99
    agent_p95_duration_ms_max: int = 8000
    llm_p95_latency_ms_max: int = 5000
    expensive_model_share_max: float = 0.01
    daily_cost_usd_max: float = 20.0

    def as_dict(self) -> dict[str, float | int]:
        return {
            "agent_success_rate_min": self.agent_success_rate_min,
            "agent_p95_duration_ms_max": self.agent_p95_duration_ms_max,
            "llm_p95_latency_ms_max": self.llm_p95_latency_ms_max,
            "expensive_model_share_max": self.expensive_model_share_max,
            "daily_cost_usd_max": self.daily_cost_usd_max,
        }


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * percentile))))
    return int(ordered[index])


def _is_success(status: Any) -> bool:
    return str(status or "").lower() in {"success", "done", "completed", "ok"}


def _is_expensive_model(model_code: str | None) -> bool:
    lowered = (model_code or "").lower()
    return any(marker in lowered for marker in EXPENSIVE_MODEL_MARKERS)


def summarize_agent_slo_cost(
    *,
    agent_runs: list[dict[str, Any]] | None = None,
    llm_calls: list[dict[str, Any]] | None = None,
    targets: AgentSLOTargets | None = None,
) -> dict[str, Any]:
    """Build a compact quality and cost dashboard payload."""

    targets = targets or AgentSLOTargets()
    agent_runs = agent_runs or []
    llm_calls = llm_calls or []

    run_count = len(agent_runs)
    successful_runs = sum(1 for run in agent_runs if _is_success(run.get("status")))
    success_rate = successful_runs / run_count if run_count else 1.0
    run_durations = [
        int(run.get("duration_ms") or 0)
        for run in agent_runs
        if int(run.get("duration_ms") or 0) > 0
    ]
    agent_p95_duration_ms = _percentile(run_durations, 0.95)

    call_count = len(llm_calls)
    llm_latencies = [
        int(call.get("latency_ms") or call.get("exec_time_ms") or 0)
        for call in llm_calls
        if int(call.get("latency_ms") or call.get("exec_time_ms") or 0) > 0
    ]
    llm_p95_latency_ms = _percentile(llm_latencies, 0.95)
    total_cost_usd = round(
        sum(
            float(
                call.get("call_cost")
                or call.get("cost_usd")
                or call.get("total_cost")
                or 0
            )
            for call in llm_calls
        ),
        6,
    )
    total_tokens = sum(
        int(
            call.get("total_tokens")
            or (
                int(call.get("input_tokens") or 0) + int(call.get("output_tokens") or 0)
            )
        )
        for call in llm_calls
    )

    model_counts: Counter[str] = Counter()
    model_costs: defaultdict[str, float] = defaultdict(float)
    expensive_calls = 0
    for call in llm_calls:
        model = str(call.get("model_code") or call.get("model") or "unknown")
        model_counts[model] += 1
        model_costs[model] += float(
            call.get("call_cost") or call.get("cost_usd") or call.get("total_cost") or 0
        )
        if _is_expensive_model(model):
            expensive_calls += 1

    expensive_model_share = expensive_calls / call_count if call_count else 0.0
    violations = []
    if success_rate < targets.agent_success_rate_min:
        violations.append("agent_success_rate_below_slo")
    if agent_p95_duration_ms > targets.agent_p95_duration_ms_max:
        violations.append("agent_p95_duration_above_slo")
    if llm_p95_latency_ms > targets.llm_p95_latency_ms_max:
        violations.append("llm_p95_latency_above_slo")
    if expensive_model_share > targets.expensive_model_share_max:
        violations.append("expensive_model_share_above_budget")
    if total_cost_usd > targets.daily_cost_usd_max:
        violations.append("daily_cost_above_budget")

    return {
        "status": "breaching" if violations else "healthy",
        "targets": targets.as_dict(),
        "metrics": {
            "agent_run_count": run_count,
            "agent_success_rate": round(success_rate, 4),
            "agent_p95_duration_ms": agent_p95_duration_ms,
            "llm_call_count": call_count,
            "llm_p95_latency_ms": llm_p95_latency_ms,
            "total_cost_usd": total_cost_usd,
            "total_tokens": total_tokens,
            "expensive_model_share": round(expensive_model_share, 4),
        },
        "model_mix": [
            {
                "model_code": model,
                "calls": count,
                "cost_usd": round(model_costs[model], 6),
            }
            for model, count in model_counts.most_common()
        ],
        "violations": violations,
    }
