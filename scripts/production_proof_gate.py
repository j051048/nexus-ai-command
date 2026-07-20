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
        "executable golden flow replay",
        "nexus_backend/app/services/golden_flow_runner.py",
        ("GoldenFlowRunner", "cross_tenant_access_denied", "missing evidence"),
    ),
    ProofCheck(
        "real isolated staging golden flow",
        "scripts/run_staging_golden_flows.py",
        (
            "STAGING_GOLDEN_ORG_ID",
            "invoke_agent",
            "submit_approval",
            "prove_tenant_isolation",
            "cleanup",
        ),
    ),
    ProofCheck(
        "atomic membership entitlement transaction",
        "supabase/migrations/20260718_membership_atomic_access.sql",
        (
            "set_subscription_access_atomic",
            "ON CONFLICT (org_id)",
            "subscription_access_versions",
            "Idempotency key",
        ),
    ),
    ProofCheck(
        "test network isolation",
        "nexus_backend/tests/conftest.py",
        ("block_unapproved_external_network", "ALLOW_TEST_NETWORK"),
    ),
    ProofCheck(
        "sensitive exception governance",
        "scripts/check_exception_governance.py",
        ("STRICT_FUNCTIONS", "admin_set_access", "_apply_cost_policy"),
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
        "migration governance",
        "scripts/check_migration_governance.py",
        ("MIGRATION_GOVERNANCE_OK", "validate_applied_checksums"),
    ),
    ProofCheck(
        "cross-table transaction governance",
        "scripts/check_transaction_contracts.py",
        ("TRANSACTION_CONTRACTS_OK", "validate_contracts", "ReplayStrategy"),
    ),
    ProofCheck(
        "gradual domain ownership governance",
        "scripts/check_domain_registry.py",
        ("DOMAIN_REGISTRY_OK", "validate_registry", "router_owners"),
    ),
    ProofCheck(
        "LLM cost hard gate",
        "scripts/check_llm_cost_policy.py",
        ("LLM_COST_POLICY_OK", "EXPENSIVE_MARKERS", "MODEL_KEYWORDS"),
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
        "scientific-instrument growth command contract",
        "nexus_backend/app/services/growth_command_service.py",
        (
            "growth-command.v1",
            "GrowthCapabilityProvider",
            "compose_growth_workspace",
            "INDUSTRY_PLAYBOOKS",
            "production_data_mixed",
        ),
    ),
    ProofCheck(
        "canonical scientific-instrument domain catalog",
        "nexus_backend/app/services/scientific_instrument_domain.py",
        (
            "scientific-instrument.v1",
            "spectroscopy",
            "chromatography",
            "mass_spectrometry",
            "energy_spectroscopy",
            "electronic_instrumentation",
            "evidence_requirements",
            "tender_focus",
        ),
    ),
    ProofCheck(
        "scientific-instrument growth schema",
        "supabase/migrations/20260718_scientific_instrument_growth_domain.sql",
        (
            "instrument_line_catalog",
            "instrument_product_catalog",
            "instrument_line_code",
            "domain_context",
            "ENABLE ROW LEVEL SECURITY",
        ),
    ),
    ProofCheck(
        "domain-aware VMD task creation",
        "nexus_backend/app/routers/vmd_tasks.py",
        (
            "CreateVMDTaskRequest",
            'router.post("")',
            "build_instrument_context",
            "target_product_models",
        ),
    ),
    ProofCheck(
        "growth command outcome-first UI",
        "src/config/growthOperatingModel.ts",
        (
            "GROWTH_WORKSPACE_ROUTES",
            "GrowthCapabilityProvider",
            "growth_outcome_events",
        ),
    ),
    ProofCheck(
        "schema convergence audit",
        "scripts/audit_schema_convergence.py",
        ("SCHEMA_CONVERGENCE_OK", "agent_heartbeat_runs", "organization_id"),
    ),
    ProofCheck(
        "agent eval baseline service",
        "nexus_backend/app/services/agent_eval_baseline_service.py",
        ("_intent_for", "run_router_baseline", "accuracy"),
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
            "persist_dashboard",
            "register_heartbeat_schedule",
            "trigger_actions",
        ),
    ),
    ProofCheck(
        "Aeon-inspired Agent Ops API",
        "nexus_backend/app/routers/ai_operating_system.py",
        (
            "/aeon-inspired-ops",
            "/aeon-inspired-ops/run-heartbeat",
            "/aeon-inspired-ops/register-heartbeat-schedule",
            "agent_ops_runtime_service",
            "focus_var",
        ),
    ),
    ProofCheck(
        "Aeon-inspired Agent Ops UI",
        "src/pages/AgentImprovementCenterPage.tsx",
        (
            "AgentOpsRuntime",
            'value="runtime"',
            "useRunAeonInspiredHeartbeat",
            "useRegisterAeonHeartbeatSchedule",
            "onRunHeartbeat",
            "onRegisterSchedule",
        ),
    ),
    ProofCheck(
        "Agent Ops system actions in inbox",
        "nexus_backend/app/routers/inbox.py",
        ("_load_system_actions", "Reactive trigger fired", '.eq("source", "system")'),
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
        "nexus_backend/app/core/transaction_contracts.py",
        (
            "TRANSACTION_CONTRACTS",
            "membership.request-decision",
            "operations.inventory-adjustment",
            "ReplayStrategy.IDEMPOTENCY_KEY",
        ),
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
        "solution commercial data foundation",
        "supabase/migrations/20260720_solution_commercial_depth.sql",
        (
            "instrument_product_catalog",
            "solution_feedback_events",
            "solution_delivery_events",
            "enterprise_connector_registry",
            "ENABLE ROW LEVEL SECURITY",
        ),
    ),
    ProofCheck(
        "evidence-grounded solution commercial service",
        "nexus_backend/app/services/solution_commercial_service.py",
        (
            "enrich_workspace_commercials",
            "extract_requirement_candidates",
            "solution_value_metrics",
            "validation_errors",
            "gross_margin_percent",
        ),
    ),
    ProofCheck(
        "solution workspace operating contract",
        "nexus_backend/app/routers/solution_workspace.py",
        (
            "/extract-requirements",
            "/create-tender",
            "/analytics",
            "/connectors",
            "search_evidence",
            "export_xlsx",
        ),
    ),
    ProofCheck(
        "knowledge asset governance contract",
        "nexus_backend/app/routers/documents.py",
        (
            '"/{document_id}/review"',
            "review_status",
            "source_version",
            "quality_score",
        ),
    ),
    ProofCheck(
        "GraphRAG P0-P2 foundation contract",
        "nexus_backend/tests/production_proof/test_graph_rag_p0_p2_contract.py",
        (
            "BusinessGraphDocument",
            "vector_hybrid_search",
            "supports_relationship_embeddings",
            "allow_dangerous_requests",
            "pending_write_count",
        ),
    ),
    ProofCheck(
        "bounded loop engineering contract",
        "nexus_backend/tests/production_proof/test_loop_engineering_contract.py",
        (
            "LoopSpec",
            "LoopBudget",
            "LoopVerifier",
            "LoopRunAudit",
            "deepseek-v4-flash",
            "ci_self_repair_loop",
            "agent_eval_regression_loop",
            "llm_cost_governor_loop",
            "model_judge_cannot_final_approve",
            "records_learned_failures",
        ),
    ),
    ProofCheck(
        "chat response acceleration contract",
        "nexus_backend/tests/production_proof/test_chat_response_acceleration_contract.py",
        (
            "three_layer_chat_path",
            "streaming_first_response",
            "parallel_context_load_budget",
            "semantic_tool_result_cache",
            "conditional_reflect_critic_policy",
            "latency_harness",
            "FastPathDecision",
            "ChatLatencyTrace",
            "deepseek-v4-flash",
            "stream_fast_path",
        ),
    ),
    ProofCheck(
        "QA last-mile contract",
        "nexus_backend/tests/production_proof/test_qa_last_mile_contract.py",
        (
            "qa_last_mile_gate.py",
            "security_severity_gate.py",
            "visual-regression.spec.ts",
            "agent_quality_thresholds",
            "RUN_VISUAL_REGRESSION",
        ),
    ),
    ProofCheck(
        "P0 source size guard",
        "scripts/check_source_size.mjs",
        ("SOURCE_SIZE_GATE_OK", "MANAGED_DEBT", "src/pages/OACenter.tsx"),
    ),
    ProofCheck(
        "Agent eval regression gate",
        "scripts/agent_eval_regression_gate.py",
        (
            "AGENT_EVAL_REGRESSION_OK",
            "baseline_scores.json",
            "agent_quality_thresholds.json",
            "regression_tolerance = 0.02",
        ),
    ),
    ProofCheck(
        "Agent SLO and cost observability",
        "nexus_backend/app/services/agent_slo_cost_service.py",
        (
            "agent_success_rate_min",
            "agent_p95_duration_ms_max",
            "expensive_model_share_max",
            "daily_cost_usd_max",
        ),
    ),
    ProofCheck(
        "canonical prompt artifact and release gate",
        "nexus_backend/app/services/prompt_artifact_service.py",
        (
            "PromptArtifact",
            "StrictPromptRenderer",
            "PromptReleaseGate",
            "REQUIRED_EVIDENCE",
            "prompt_artifact_resolver",
        ),
    ),
    ProofCheck(
        "global context compiler and evidence contract",
        "nexus_backend/app/agent/context_compiler.py",
        (
            "ContextCompilePolicy",
            "system_budget",
            "mandatory",
            "utility",
            "evidence_ids",
        ),
    ),
    ProofCheck(
        "full graph replay assertions",
        "nexus_backend/app/services/full_graph_replay_service.py",
        (
            "get_agent_graph().run",
            "agent_replay_harness.evaluate_trace",
            "evidence_contract",
            "side_effects",
        ),
    ),
    ProofCheck(
        "full graph replay API",
        "nexus_backend/app/routers/agent_replay.py",
        ("/run-case", "require_agent_ops", "full_graph_replay_service.run_case"),
    ),
    ProofCheck(
        "scientific instrument Agent eval",
        "nexus_backend/evals/datasets/scientific_instrument_agent_cases.json",
        (
            "instrument_calibration",
            "predictive_maintenance",
            "lab_compliance",
            "instrument_telemetry",
        ),
    ),
    ProofCheck(
        "scientific solution operational schema",
        "supabase/migrations/20260721_solution_workspace_operational_depth.sql",
        (
            "solution_price_books",
            "solution_commercial_approvals",
            "solution_review_comments",
            "solution_quality_eval_runs",
            "request_key",
        ),
    ),
    ProofCheck(
        "scientific solution operational services",
        "nexus_backend/app/routers/solution_workspace_ops.py",
        (
            "cpq-preview",
            "commercial-approvals",
            "rewrite-section",
            "tender-readiness",
            "learning-insights",
            "deliver",
        ),
    ),
    ProofCheck(
        "scientific solution real staging flow",
        "scripts/run_staging_golden_flows.py",
        (
            "prove_solution_workflow",
            "solution.generate",
            "solution.evaluate",
            "solution.tender_readiness",
            "solution.export",
        ),
    ),
    ProofCheck(
        "production proof wired to CI",
        ".github/workflows/ci.yml",
        ("production_proof_gate.py", "tests/production_proof"),
    ),
]


def validate_golden_flow_count() -> tuple[bool, str]:
    flows = json.loads(
        (
            ROOT
            / "nexus_backend/tests/production_proof/fixtures/golden_business_flows.json"
        ).read_text(encoding="utf-8")
    )
    if len(flows) < 5:
        return False, "golden flow count below 5"
    return True, ""


def validate_agent_eval_case_count() -> tuple[bool, str]:
    cases = json.loads(
        (
            ROOT
            / "nexus_backend/tests/production_proof/fixtures/agent_eval_cases_200.json"
        ).read_text(encoding="utf-8")
    )
    if len(cases) < 200:
        return False, "agent eval case count below 200"
    return True, ""


def validate_solution_eval_case_count() -> tuple[bool, str]:
    dataset = json.loads(
        (ROOT / "nexus_backend/evals/datasets/solution_quality_cases.json").read_text(
            encoding="utf-8"
        )
    )
    if len(dataset.get("cases") or []) < 12:
        return False, "solution eval case count below 12"
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

    ok, reason = validate_solution_eval_case_count()
    print(f"{'OK' if ok else 'FAIL':<4} solution eval case count")
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
