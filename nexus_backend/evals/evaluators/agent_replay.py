"""Replay-based agent evaluator.

Unlike keyword-only evaluators, this checks recorded LangGraph traces or
deterministic cassettes with the same assertion harness used by ops tooling.
"""

from __future__ import annotations

from typing import Any

from app.services.agent_replay_harness import agent_replay_harness
from evals.eval_metrics import EvalDimension, EvalResult


class AgentReplayEvaluator:
    dimension = EvalDimension.TASK_COMPLETION

    async def evaluate(self, case: dict[str, Any]) -> EvalResult:
        trace_data = case.get("trace") or case.get("cassette") or {}
        expectations = case.get("expectations") or {}
        result = agent_replay_harness.evaluate_trace(trace_data, expectations)
        return EvalResult(
            case_id=case.get("id", "unknown"),
            dimension=self.dimension,
            passed=result.passed,
            score=result.score,
            details=result.to_dict(),
        )
