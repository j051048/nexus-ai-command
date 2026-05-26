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
        "local pytest launcher",
        "scripts/dev_pytest.ps1",
        ("PYTHONIOENCODING", "PYTHONPATH", "-m pytest"),
    ),
    ProofCheck(
        "last mile check runner",
        "scripts/run_last_mile_checks.ps1",
        ("RealBackend", "RealMigrations", "verify_migration_replay.py"),
    ),
    ProofCheck(
        "memory-safe frontend build wrapper",
        "scripts/build_frontend.mjs",
        ("--max-old-space-size", "VITE_BUILD_PROFILE", "vite"),
    ),
    ProofCheck(
        "large agent eval dataset",
        "nexus_backend/tests/production_proof/fixtures/agent_eval_cases_200.json",
        ("agent-eval-200", "vmd_campaign", "respects_tenant_context"),
    ),
    ProofCheck(
        "tool failure attribution",
        "nexus_backend/app/agent/tool_failure_attribution.py",
        ("invalid_params", "permission_denied", "network_error", "suggested_action"),
    ),
    ProofCheck(
        "AI weekly behavior report API",
        "nexus_backend/app/routers/dashboard.py",
        ('"/ai-weekly-report"', "audit_summary", "human_overrides"),
    ),
    ProofCheck(
        "AI weekly behavior report UI hook",
        "src/hooks/useAIWeeklyReport.ts",
        ("ai-weekly-report", "human_overrides", "estimated_hours_saved"),
    ),
    ProofCheck(
        "module convergence policy",
        "src/config/featureFlags.ts",
        ("MODULE_FOCUS_POLICY", "THIRD_PARTY_FIRST_MODULES", "isThirdPartyFirstModule"),
    ),
    ProofCheck(
        "Aeon-inspired Agent Ops runtime",
        "nexus_backend/app/services/agent_ops_runtime_service.py",
        (
            "build_heartbeat",
            "build_skill_health",
            "build_reactive_triggers",
            "build_self_repair",
            "build_skill_chains",
            "build_universal_var",
            "build_operating_memory",
            "build_instance_fleet",
            "build_persona_soul",
            "build_external_capabilities",
        ),
    ),
    ProofCheck(
        "Aeon-inspired Agent Ops API",
        "nexus_backend/app/routers/ai_operating_system.py",
        ("/aeon-inspired-ops", "agent_ops_runtime_service", "focus_var"),
    ),
    ProofCheck(
        "Aeon-inspired Agent Ops UI",
        "src/pages/AgentImprovementCenterPage.tsx",
        ("Aeon-style Agent Ops Runtime", "Heartbeat Supervisor", "MCP / A2A Capabilities"),
    ),
    ProofCheck(
        "Aeon-inspired Agent Ops persistence",
        "supabase/migrations/20260526_agent_ops_runtime.sql",
        ("agent_heartbeat_runs", "agent_skill_health", "agent_external_capabilities"),
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


def validate_agent_eval_case_count() -> tuple[bool, str]:
    cases = json.loads(
        (ROOT / "nexus_backend/tests/production_proof/fixtures/agent_eval_cases_200.json").read_text(
            encoding="utf-8"
        )
    )
    if len(cases) < 200:
        return False, "agent eval case count below 200"
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

    ok, reason = validate_agent_eval_case_count()
    print(f"{'OK' if ok else 'FAIL':<4} agent eval case count")
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
