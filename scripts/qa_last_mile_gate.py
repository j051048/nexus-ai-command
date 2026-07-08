"""Offline QA last-mile gate.

This script makes the five missing QA controls explicit and CI-checkable:
1. staging golden path contract;
2. chat acceleration latency budget contract;
3. agent eval quality thresholds;
4. frontend core-page visual regression contract;
5. security severity policy contract.

It is intentionally offline. Real staging execution and screenshot comparison
remain opt-in through environment flags so normal PR CI stays deterministic.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

GOLDEN_FLOW_IDS = {
    "golden-login-crm-ai-approval-close",
    "golden-stale-customer-next-best-action",
    "golden-tender-score-to-boss-review",
    "golden-contract-renewal-risk",
    "golden-cross-tenant-deny",
}

CHAT_LATENCY_BUDGETS_MS = {
    "fast_path_ttfb": 1000,
    "semantic_cache_ttfb": 1000,
    "standard_path_first_event": 1500,
    "context_load": 800,
    "deep_agent_progress_event": 2500,
}

AGENT_THRESHOLD_KEYS = {
    "intent_accuracy_min",
    "tool_selection_accuracy_min",
    "groundedness_min",
    "tenant_context_accuracy_min",
    "cost_regression_max_pct",
    "latency_regression_max_pct",
}

CORE_VISUAL_ROUTES = {
    "/dashboard",
    "/crm",
    "/approval",
    "/contracts",
    "/ai-operating-system",
}


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def load_json(path: str) -> Any:
    return json.loads(read(path))


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def check_staging_golden_paths(failures: list[str]) -> None:
    flows = load_json(
        "nexus_backend/tests/production_proof/fixtures/golden_business_flows.json"
    )
    ids = {flow.get("id") for flow in flows}
    require(
        GOLDEN_FLOW_IDS.issubset(ids),
        "staging golden path contract is missing one or more golden flow ids",
        failures,
    )
    require(len(flows) >= 5, "staging golden path count is below 5", failures)
    for flow in flows:
        require(bool(flow.get("steps")), f"{flow.get('id')} has no steps", failures)
        for step in flow.get("steps", []):
            require(
                bool(step.get("asserts")),
                f"{flow.get('id')}:{step.get('action')} has no asserts",
                failures,
            )

    workflow = read(".github/workflows/test-full.yml")
    for token in (
        "RUN_REAL_STAGING_GOLDEN_PATHS",
        "STAGING_API_URL",
        "STAGING_TEST_TOKEN",
        "STAGING_ORG_ID",
    ):
        require(
            token in workflow,
            f"test-full workflow missing staging opt-in token {token}",
            failures,
        )


def check_chat_latency_budget(failures: list[str]) -> None:
    service = read("nexus_backend/app/services/chat_response_acceleration_service.py")
    for token in (
        "ChatLatencyTrace",
        "FastPathDecision",
        "ContextLoadBudget",
        "time_to_first_token",
        "semantic_tool_result_cache",
        "conditional_reflect_critic_policy",
        "deepseek-v4-flash",
    ):
        require(token in service, f"chat acceleration service missing {token}", failures)

    for name, budget in CHAT_LATENCY_BUDGETS_MS.items():
        require(budget > 0, f"invalid latency budget for {name}", failures)
    require(
        CHAT_LATENCY_BUDGETS_MS["fast_path_ttfb"] <= 1000,
        "fast path TTFB budget must stay at or below 1000ms",
        failures,
    )


def check_agent_quality_thresholds(failures: list[str]) -> None:
    cases = load_json(
        "nexus_backend/tests/production_proof/fixtures/agent_eval_cases_200.json"
    )
    thresholds = load_json(
        "nexus_backend/tests/production_proof/fixtures/agent_quality_thresholds.json"
    )
    require(len(cases) >= 200, "agent eval dataset is below 200 cases", failures)

    configured = set(thresholds.get("thresholds", {}))
    missing = sorted(AGENT_THRESHOLD_KEYS - configured)
    require(not missing, f"agent quality thresholds missing keys: {missing}", failures)

    for key, value in thresholds.get("thresholds", {}).items():
        if key.endswith("_min"):
            require(0 < value <= 1, f"{key} must be in (0, 1]", failures)
        if key.endswith("_max_pct"):
            require(0 <= value <= 100, f"{key} must be in [0, 100]", failures)

    proof_tests = read("nexus_backend/tests/production_proof/test_agent_quality_baselines.py")
    require(
        "agent_quality_thresholds" in proof_tests,
        "agent quality proof tests do not consume agent_quality_thresholds",
        failures,
    )


def check_visual_regression_contract(failures: list[str]) -> None:
    visual_spec = read("e2e/visual-regression.spec.ts")
    workflow = read(".github/workflows/test-full.yml")
    for token in (
        "RUN_VISUAL_REGRESSION",
        "toHaveScreenshot",
        "setupBusinessMocks",
        "mockLoggedInState",
    ):
        require(token in visual_spec, f"visual regression spec missing {token}", failures)

    for route in CORE_VISUAL_ROUTES:
        require(route in visual_spec, f"visual regression spec missing {route}", failures)

    require(
        "visual-regression.spec.ts" in workflow,
        "test-full workflow does not reference visual-regression.spec.ts",
        failures,
    )
    require(
        "RUN_VISUAL_REGRESSION" in workflow,
        "test-full workflow missing RUN_VISUAL_REGRESSION opt-in",
        failures,
    )


def check_security_severity_policy(failures: list[str]) -> None:
    policy = read("scripts/security_severity_gate.py")
    workflow = read(".github/workflows/test-full.yml")
    for token in (
        "critical",
        "high",
        "medium",
        "low",
        "npm audit --omit=dev --audit-level=critical",
        "pip-audit",
        "scan_hardcoded_secrets.py",
        "Trivy",
    ):
        require(token in policy, f"security severity policy missing {token}", failures)
    require(
        "security_severity_gate.py" in workflow,
        "test-full workflow does not run security severity policy gate",
        failures,
    )


def main() -> int:
    checks = [
        ("staging golden paths", check_staging_golden_paths),
        ("chat latency budget", check_chat_latency_budget),
        ("agent eval quality thresholds", check_agent_quality_thresholds),
        ("visual regression contract", check_visual_regression_contract),
        ("security severity policy", check_security_severity_policy),
    ]
    failures: list[str] = []
    print("QA last-mile gate")
    for name, check in checks:
        before = len(failures)
        check(failures)
        print(f"{'OK' if len(failures) == before else 'FAIL':<4} {name}")

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
