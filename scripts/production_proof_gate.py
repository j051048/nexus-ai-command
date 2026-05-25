"""Production proof gate.

This gate turns the audit recommendations into repository-level invariants.
It is intentionally offline: real Supabase/LLM execution is opt-in through the
pytest production_proof tests and CI environment variables.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ProofCheck:
    name: str
    path: str
    tokens: tuple[str, ...] = ()


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def run_check(check: ProofCheck) -> tuple[bool, str]:
    target = ROOT / check.path
    if not target.exists():
        return False, f"missing {check.path}"
    content = read(check.path)
    missing = [token for token in check.tokens if token not in content]
    if missing:
        return False, f"missing token(s): {', '.join(missing)}"
    return True, ""


CHECKS = [
    ProofCheck(
        "five golden business flows",
        "nexus_backend/tests/production_proof/fixtures/golden_business_flows.json",
        (
            "golden-login-crm-ai-approval-close",
            "golden-stale-customer-next-best-action",
            "golden-tender-score-to-boss-review",
            "golden-contract-renewal-risk",
            "golden-cross-tenant-deny",
        ),
    ),
    ProofCheck(
        "agent graph e2e contract",
        "nexus_backend/tests/production_proof/test_agent_graph_e2e_contract.py",
        ("graph.ainvoke", "RUN_REAL_AGENT_GRAPH_E2E", "expected_tool_calls"),
    ),
    ProofCheck(
        "tenant RLS isolation contract",
        "nexus_backend/tests/production_proof/test_tenant_rls_isolation_contract.py",
        ("OrgFilteredClient", "RUN_REAL_RLS_PROOF", "organization_id"),
    ),
    ProofCheck(
        "classifier baseline",
        "nexus_backend/tests/production_proof/fixtures/intent_baseline.json",
        ("crm_followup", "approval_decision", "tender_support", "battlecard"),
    ),
    ProofCheck(
        "tool error matrix",
        "nexus_backend/tests/production_proof/test_tool_error_matrix_contract.py",
        ("invalid_params", "permission_denied", "timeout"),
    ),
    ProofCheck(
        "migration replay contract",
        "nexus_backend/tests/production_proof/test_migration_replay_contract.py",
        ("verify_staging_migrations.py", "CREATE TABLE IF NOT EXISTS"),
    ),
    ProofCheck(
        "migration schema conflict scanner",
        "scripts/scan_migration_schema_conflicts.py",
        ("schema-compatible", "extract_definitions", "CREATE_RE"),
    ),
    ProofCheck(
        "RLS policy column scanner",
        "scripts/scan_rls_policy_columns.py",
        ("TENANT_COLUMN_RE", "current_tenant_id_text", "is not defined"),
    ),
    ProofCheck(
        "scratch migration replay command",
        "scripts/verify_migration_replay.py",
        ("MIGRATION_REPLAY_DATABASE_URL", "ON_ERROR_STOP=1", "psql"),
    ),
    ProofCheck(
        "local Python runtime launcher",
        "scripts/dev_python.ps1",
        ("trying global Python", "No Python runtime found"),
    ),
    ProofCheck(
        "SSE reconnect contract",
        "nexus_backend/tests/production_proof/test_sse_reconnect_contract.py",
        ("disconnect_detection", "idempotent_resume", "no_duplicate_message"),
    ),
    ProofCheck(
        "API client unification contract",
        "nexus_backend/tests/production_proof/test_api_client_and_transaction_contract.py",
        ("httpClient", "aiClient", "single default transport"),
    ),
    ProofCheck(
        "transaction RPC contract",
        "nexus_backend/tests/production_proof/test_api_client_and_transaction_contract.py",
        ("SECURITY DEFINER", "approval", "p_org_id"),
    ),
    ProofCheck(
        "capacity/load contract",
        "nexus_backend/tests/production_proof/test_load_and_capacity_contract.py",
        ("k6", "/api/chat", "test_load.py"),
    ),
    ProofCheck(
        "LLM VCR replay cassette",
        "nexus_backend/tests/production_proof/fixtures/llm_replay_cassette.json",
        ("cassette_version", "expected_tool_calls", "recorded_response"),
    ),
    ProofCheck(
        "known failure regression contracts",
        "nexus_backend/tests/production_proof/test_known_failure_regressions.py",
        ("_kingdee_identity", "PROMPT_FIREWALL_LLM_JUDGE", "chat-input"),
    ),
    ProofCheck(
        "product focus and observability contract",
        "nexus_backend/tests/production_proof/test_product_focus_and_observability_contract.py",
        ("MODULE_TIER_LABELS", "reward_model", "audit_summary"),
    ),
    ProofCheck(
        "production proof wired to CI",
        ".github/workflows/ci.yml",
        ("production_proof_gate.py", "tests/production_proof"),
    ),
]


def validate_golden_flow_count() -> tuple[bool, str]:
    flows = json.loads(
        (ROOT / "nexus_backend/tests/production_proof/fixtures/golden_business_flows.json").read_text(
            encoding="utf-8"
        )
    )
    if len(flows) < 5:
        return False, "golden flow count below 5"
    return True, ""


def main() -> int:
    failures: list[str] = []
    print("Production proof gate")
    for check in CHECKS:
        ok, reason = run_check(check)
        print(f"{'OK' if ok else 'FAIL':<4} {check.name}")
        if not ok:
            failures.append(f"{check.name}: {reason}")

    ok, reason = validate_golden_flow_count()
    print(f"{'OK' if ok else 'FAIL':<4} golden flow count")
    if not ok:
        failures.append(reason)

    if failures:
        print("\nFailures:")
        for item in failures:
            print(f" - {item}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
