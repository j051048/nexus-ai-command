"""Deterministic replay assertions for real agent traces and cassettes."""

from __future__ import annotations

import re
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

        expected_tool_args = expectations.get("expected_tool_args") or {}
        if expected_tool_args:
            actual_calls = self._collect_tool_calls(steps)
            failures = []
            for tool_name, subset in expected_tool_args.items():
                calls = [call for call in actual_calls if call["name"] == tool_name]
                if not any(self._dict_contains(call["args"], subset) for call in calls):
                    failures.append({"tool": tool_name, "expected_subset": subset})
            add(
                "tool_arguments",
                not failures,
                {"failures": failures, "actual": actual_calls},
            )

        state_equals = expectations.get("state_equals") or {}
        if state_equals:
            final_state = trace_data.get("final_state") or {}
            mismatches = {
                key: {"expected": value, "actual": final_state.get(key)}
                for key, value in state_equals.items()
                if final_state.get(key) != value
            }
            add("final_state", not mismatches, {"mismatches": mismatches})

        required_side_effects = expectations.get("required_side_effects") or []
        forbidden_side_effects = expectations.get("forbidden_side_effects") or []
        if required_side_effects or forbidden_side_effects:
            side_effects = trace_data.get("side_effects") or []
            effect_types = {
                str(item.get("type") if isinstance(item, dict) else item)
                for item in side_effects
            }
            missing = sorted(set(required_side_effects) - effect_types)
            forbidden_hits = sorted(
                set(forbidden_side_effects).intersection(effect_types)
            )
            add(
                "side_effects",
                not missing and not forbidden_hits,
                {
                    "missing": missing,
                    "forbidden_hits": forbidden_hits,
                    "actual": sorted(effect_types),
                },
            )

        if "requires_hitl" in expectations:
            actual_hitl = bool(
                trace_data.get("hitl_required")
                or (trace_data.get("final_state") or {}).get("requires_confirmation")
                or any(
                    str(step.get("status") or "").lower()
                    in {"blocked", "awaiting_confirmation"}
                    for step in steps
                )
            )
            add(
                "hitl_gate",
                actual_hitl is bool(expectations["requires_hitl"]),
                {
                    "expected": bool(expectations["requires_hitl"]),
                    "actual": actual_hitl,
                },
            )

        required_evidence_ids = expectations.get("required_evidence_ids") or []
        if required_evidence_ids:
            contract = (
                trace_data.get("evidence_contract")
                or (trace_data.get("final_state") or {}).get("evidence_contract")
                or {}
            )
            actual_ids = set(contract.get("evidence_ids") or [])
            add(
                "evidence_contract",
                set(required_evidence_ids).issubset(actual_ids),
                {"expected": required_evidence_ids, "actual": sorted(actual_ids)},
            )

        final_contains = expectations.get("final_contains") or []
        if final_contains:
            final_response = trace_data.get("final_response") or ""
            add(
                "final_response",
                all(item in final_response for item in final_contains),
                {"expected_contains": final_contains, "actual": final_response[:500]},
            )

        final_regex = expectations.get("final_regex")
        if final_regex:
            final_response = trace_data.get("final_response") or ""
            add(
                "final_response_regex",
                re.search(final_regex, final_response) is not None,
                {"pattern": final_regex, "actual": final_response[:500]},
            )

        max_errors = expectations.get("max_errors")
        if max_errors is not None:
            error_count = sum(
                1
                for step in steps
                if step.get("error") or str(step.get("status") or "").lower() == "error"
            )
            add(
                "error_budget",
                error_count <= int(max_errors),
                {"max": int(max_errors), "actual": error_count},
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

    @staticmethod
    def _collect_tool_calls(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        for step in steps:
            sources = [step.get("tool_calls") or []]
            output = step.get("output_data") or step.get("output_snapshot") or {}
            sources.append(output.get("tool_calls") or [])
            for source in sources:
                for call in source:
                    calls.append(
                        {
                            "name": call.get("tool_name") or call.get("name"),
                            "args": call.get("tool_args")
                            or call.get("args")
                            or call.get("arguments")
                            or {},
                        }
                    )
        return calls

    @classmethod
    def _dict_contains(cls, actual: Any, expected: Any) -> bool:
        if isinstance(expected, dict):
            return isinstance(actual, dict) and all(
                key in actual and cls._dict_contains(actual[key], value)
                for key, value in expected.items()
            )
        if isinstance(expected, list):
            return isinstance(actual, list) and all(item in actual for item in expected)
        return actual == expected


agent_replay_harness = AgentReplayHarness()
