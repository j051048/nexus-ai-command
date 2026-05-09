"""Offline shadow evaluation helpers for prompt/model changes."""

from __future__ import annotations

from typing import Any

from app.services.agent_replay_harness import agent_replay_harness


class ShadowEvalService:
    async def compare_trace_to_expectations(
        self,
        *,
        trace_data: dict[str, Any],
        candidate_metadata: dict[str, Any] | None = None,
        expectations: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        expectations = expectations or self._derive_expectations(trace_data)
        result = agent_replay_harness.evaluate_trace(trace_data, expectations)
        return {
            "candidate": candidate_metadata or {},
            "baseline_trace_id": trace_data.get("trace_id"),
            "passed": result.passed,
            "score": result.score,
            "checks": result.checks,
            "expectations": expectations,
        }

    def _derive_expectations(self, trace_data: dict[str, Any]) -> dict[str, Any]:
        steps = trace_data.get("steps") or trace_data.get("steps_json") or []
        nodes = [s.get("node_type") for s in steps if s.get("node_type")]
        tools = []
        for step in steps:
            for call in step.get("tool_calls") or []:
                name = call.get("name") or call.get("tool_name")
                if name:
                    tools.append(name)
        return {
            "expected_nodes": nodes,
            "expected_tools": sorted(set(tools)),
            "max_tokens": int((trace_data.get("total_tokens") or 0) * 1.15) + 1,
            "max_duration_ms": int((trace_data.get("total_duration_ms") or 0) * 1.25)
            + 1000,
        }


shadow_eval_service = ShadowEvalService()
