"""Evaluate recorded, real-model artifact outputs against a golden contract."""

from __future__ import annotations

import re
from typing import Any

_CITATION = re.compile(r"\[(?:EVID|证据)[:：][^\]]+\]", re.IGNORECASE)


def evaluate_artifact_output(
    case: dict[str, Any], output: dict[str, Any]
) -> dict[str, Any]:
    text = str(output.get("content") or output.get("content_markdown") or "")
    missing_sections = [
        item for item in case.get("expected_sections") or [] if str(item) not in text
    ]
    missing_terms = [
        item for item in case.get("required_terms") or [] if str(item) not in text
    ]
    forbidden_hits = [
        item for item in case.get("forbidden_terms") or [] if str(item) in text
    ]
    minimum = int(case.get("minimum_character_count") or 0)
    failures = []
    if len(text) < minimum:
        failures.append(f"content_too_short:{len(text)}<{minimum}")
    if missing_sections:
        failures.append("missing_sections:" + ",".join(map(str, missing_sections)))
    if missing_terms:
        failures.append("missing_terms:" + ",".join(map(str, missing_terms)))
    if forbidden_hits:
        failures.append("forbidden_claims:" + ",".join(map(str, forbidden_hits)))
    if not _CITATION.search(text):
        failures.append("citation_missing")
    return {
        "case_id": case.get("id"),
        "passed": not failures,
        "failures": failures,
        "character_count": len(text),
        "model": output.get("model"),
        "latency_ms": output.get("latency_ms"),
        "cost_usd": output.get("cost_usd"),
    }


def evaluate_artifact_output_run(
    cases: list[dict[str, Any]], outputs: list[dict[str, Any]]
) -> dict[str, Any]:
    output_by_id = {str(item.get("case_id")): item for item in outputs}
    results = []
    for case in cases:
        output = output_by_id.get(str(case.get("id")))
        if output is None:
            results.append(
                {
                    "case_id": case.get("id"),
                    "passed": False,
                    "failures": ["recorded_output_missing"],
                }
            )
        else:
            results.append(evaluate_artifact_output(case, output))
    passed = sum(int(item["passed"]) for item in results)
    latencies = [
        float(item["latency_ms"])
        for item in results
        if item.get("latency_ms") is not None
    ]
    costs = [
        float(item["cost_usd"]) for item in results if item.get("cost_usd") is not None
    ]
    return {
        "schema_version": "artifact-output-eval.v1",
        "case_count": len(results),
        "passed": passed,
        "pass_rate": round(passed / len(results), 4) if results else 0.0,
        "average_latency_ms": (
            round(sum(latencies) / len(latencies), 2) if latencies else None
        ),
        "total_cost_usd": round(sum(costs), 6) if costs else None,
        "results": results,
    }
