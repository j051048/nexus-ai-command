"""Offline CI gate for AI route quality and cost containment."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "nexus_backend"
sys.path.insert(0, str(BACKEND))

from app.services.ai_execution_policy_service import (  # noqa: E402
    AIExecutionPolicy,
    assess_task,
    effective_policy_for_task,
)


def main() -> int:
    fixture = BACKEND / "tests" / "fixtures" / "ai_execution_policy_cases.json"
    cases = json.loads(fixture.read_text(encoding="utf-8"))
    correct = 0
    total_calls = 0
    expensive_calls = 0

    for case in cases:
        configured = AIExecutionPolicy.for_mode("balanced")
        configured.high_risk_terms = case.get("high_risk_terms", [])
        profile = assess_task(
            case["query"],
            complexity=case["complexity"],
            requires_tools=case["requires_tools"],
            scheduled=case.get("scheduled", False),
            policy=configured,
        )
        policy = effective_policy_for_task(configured, profile)
        correct += int(
            profile.risk_level.value == case["expected_risk"]
            and profile.execution_depth == case["expected_depth"]
        )
        planned_calls = {"direct": 1, "verify": 2, "critic": 3}[
            profile.execution_depth
        ]
        total_calls += min(planned_calls, policy.max_calls)
        expensive_calls += int(policy.primary_model != "deepseek-v4-flash")

    accuracy = correct / len(cases)
    average_calls = total_calls / len(cases)
    expensive_share = expensive_calls / len(cases)

    print("AI execution policy gate")
    print(f"route_accuracy={accuracy:.2%}")
    print(f"average_planned_calls={average_calls:.2f}")
    print(f"expensive_model_share={expensive_share:.2%}")

    failures: list[str] = []
    if accuracy < 0.95:
        failures.append("route accuracy below 95%")
    # The fixture intentionally over-represents approvals and destructive
    # operations; keep the cap below the three-call strict path.
    if average_calls > 2.5:
        failures.append("average planned calls above 2.50")
    if expensive_share > 0:
        failures.append("automatic expensive model routing detected")
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("AI_EXECUTION_POLICY_GATE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
