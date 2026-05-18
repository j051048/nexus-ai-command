"""Deterministic replay assertions for real agent traces and cassettes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReplayHarnessResult:
    passed: bool
    score: float
    checks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "score": self.score,
            "checks": self.checks,
        }


class AgentReplayHarness:
    """Evaluate a replay trace against deterministic expectations."""

    def evaluate_trace(
        self,
        trace_data: dict[str, Any],
        expectations: dict[str, Any],
    ) -> ReplayHarnessResult:
        steps = trace_data.get("steps") or trace_data.get("steps_json") or []
        checks: list[dict[str, Any]] = []

        def add(name: str, passed: bool, details: dict[str, Any] | None = None):
            checks.append({"name": name, "passed": passed, "details": details or {}})

        expected_nodes = expectations.get("expected_nodes")
        if expected_nodes:
            actual_nodes = [s.get("node_type") or s.get("node_name") for s in steps]
            add(
                "node_sequence",
                self._contains_ordered(actual_nodes, expected_nodes),
                {"expected": expected_nodes, "actual": actual_nodes},
            )

        expected_tools = expectations.get("expected_tools") or []
        if expected_tools:
            actual_tools = self._collect_tool_names(steps)
            add(
                "tool_calls",
                set(expected_tools).issubset(set(actual_tools)),
                {"expected": expected_tools, "actual": actual_tools},
            )

        forbidden_tools = expectations.get("forbidden_tools") or []
        if forbidden_tools:
            actual_tools = self._collect_tool_names(steps)
            add(
                "forbidden_tools",
                not set(forbidden_tools).intersection(set(actual_tools)),
                {"forbidden": forbidden_tools, "actual": actual_tools},
            )

        final_contains = expectations.get("final_contains") or []
        if final_contains:
            final_response = trace_data.get("final_response") or ""
            add(
                "final_response",
                all(item in final_response for item in final_contains),
                {"expected_contains": final_contains, "actual": final_response[:500]},
            )

        max_tokens = expectations.get("max_tokens")
        if max_tokens is not None:
            actual = trace_data.get("total_tokens") or 0
            add(
                "token_budget",
                actual <= max_tokens,
                {"max": max_tokens, "actual": actual},
            )

        max_duration_ms = expectations.get("max_duration_ms")
        if max_duration_ms is not None:
            actual = trace_data.get("total_duration_ms") or 0
            add(
                "latency_budget",
                actual <= max_duration_ms,
                {"max": max_duration_ms, "actual": actual},
            )

        if not checks:
            add("non_empty_trace", bool(steps), {"steps": len(steps)})

        passed_count = sum(1 for c in checks if c["passed"])
        score = passed_count / len(checks) if checks else 0.0
        return ReplayHarnessResult(
            passed=bool(checks) and passed_count == len(checks),
            score=score,
            checks=checks,
        )

    @staticmethod
    def _contains_ordered(actual: list[str], expected: list[str]) -> bool:
        pos = 0
        for item in actual:
            if pos < len(expected) and item == expected[pos]:
                pos += 1
        return pos == len(expected)

    @staticmethod
    def _collect_tool_names(steps: list[dict[str, Any]]) -> list[str]:
        names: list[str] = []
        for step in steps:
            for call in step.get("tool_calls") or []:
                name = call.get("tool_name") or call.get("name")
                if name:
                    names.append(name)
            output = step.get("output_data") or step.get("output_snapshot") or {}
            for call in output.get("tool_calls") or []:
                name = call.get("tool_name") or call.get("name")
                if name:
                    names.append(name)
        return names


agent_replay_harness = AgentReplayHarness()
