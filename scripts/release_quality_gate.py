"""Static P0-P6 release quality gate.

This script intentionally avoids network and database access. It verifies that
the repository still contains the launch-critical controls that are easy to
regress during fast product work.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class GateCheck:
    level: str
    name: str
    path: str
    tokens: tuple[str, ...] = ()
    severity: str = "critical"


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def file_exists(path: str) -> bool:
    return (ROOT / path).exists()


def run_check(check: GateCheck) -> tuple[bool, str]:
    target = ROOT / check.path
    if not target.exists():
        return False, f"missing file: {check.path}"
    if not check.tokens:
        return True, ""
    content = read_text(check.path)
    missing = [token for token in check.tokens if token not in content]
    if missing:
        return False, f"missing token(s) in {check.path}: {', '.join(missing)}"
    return True, ""


CHECKS = [
    # P0: production survivability and launch blast-radius controls.
    GateCheck("P0", "production readiness script", "scripts/production_readiness_check.mjs", ("developer tools disabled", "golden smoke route:")),
    GateCheck("P0", "production health checker", "scripts/production_health_check.mjs", ("/health/live", "/health/ready", "HEALTH_CHECK_TOKEN")),
    GateCheck("P0", "static RLS coverage scanner", "scripts/scan_rls_coverage.py", ("MISSING_POLICY", "_collect_policy_tables")),
    GateCheck("P0", "containerized backend build", "Dockerfile", ("COPY nexus_backend/requirements.txt", "USER appuser")),
    GateCheck("P0", "local deployment composition", "docker-compose.yml", ("celery-worker", "redis")),
    GateCheck("P0", "customer launch module manifest", "src/config/customerLaunchModules.ts", ("owner:", "smokePath:")),
    GateCheck("P0", "top 10 E2E smoke suite", "e2e/top10-critical-flows.spec.ts", ("/login", "/crm", "/approval", "/finance", "/workflows")),
    GateCheck("P0", "document embedding vector index", "supabase/migrations/20260514_p0_document_embeddings_vector_index.sql", ("vector_cosine_ops",)),
    GateCheck("P0", "tenant RLS policy backfill", "supabase/migrations/20260514_p0_tenant_rls_policy_backfill.sql", ("current_tenant_id_text", "CREATE POLICY")),
    GateCheck("P0", "immutable audit log trigger", "supabase/migrations/20260419_p1_audit_logs_immutable.sql", ("prevent_audit_log_mutation", "BEFORE UPDATE OR DELETE")),
    GateCheck("P0", "celery backlog health", "nexus_backend/app/core/celery_queue_monitor.py", ("CELERY_QUEUE_DEPTH_WARNING", "observe_celery_queue_depth")),
    # P1: operational correctness, cost visibility, and UX hardening.
    GateCheck("P1", "bounded idempotency fallback", "nexus_backend/app/core/idempotency_middleware.py", ("IDEMPOTENCY_MEMORY_FALLBACK_MAX", "process-local memory fallback")),
    GateCheck("P1", "streaming usage estimation fallback", "nexus_backend/app/services/llm_adapters/openai_compatible.py", ("_estimate_stream_usage", '"estimated": True')),
    GateCheck("P1", "route suspense and error boundary", "src/components/common/ModuleRouteBoundary.tsx", ("Suspense", "ModuleErrorBoundary", "ModuleRouteSkeleton")),
    GateCheck("P1", "agent observability API", "nexus_backend/app/routers/agent_observability.py", ("/quality/trends", "/shadow-eval", "/context-ablation")),
    GateCheck("P1", "semantic Tool RAG binding", "nexus_backend/app/agent/plan/tool_binding.py", ("tool_embedding_index.retrieve",)),
    GateCheck("P1", "tool governance API", "nexus_backend/app/routers/chat.py", ("/tools/governance", "/tools/rag/evaluate")),
    GateCheck("P1", "tool developer guide", "docs/TOOL_DEVELOPMENT_GUIDE.md", ("required_role", "risk", "Tool RAG")),
    # P2: enterprise sales readiness without requiring external vendors.
    GateCheck("P2", "enterprise SSO routes", "nexus_backend/app/routers/enterprise_sso.py", ("oidc", "saml")),
    GateCheck("P2", "enterprise SSO signed state", "nexus_backend/app/services/enterprise_sso_service.py", ("sign_state", "verify_state", "parse_saml_response")),
    GateCheck("P2", "API key hard-fail middleware", "nexus_backend/app/core/api_key_middleware.py", ("Invalid API key", "never silently downgraded")),
    GateCheck("P2", "deny-by-default tool RBAC", "nexus_backend/app/core/tool_rbac.py", ("Deny-by-default guard", "_SAFE_ALL_PREFIXES")),
    GateCheck("P2", "compliance audit export API", "nexus_backend/app/routers/compliance.py", ("/audit/export", "csv")),
    GateCheck("P2", "SOC2 controls map", "docs/SOC2_CONTROLS.md", ("CC6", "CC7", "Evidence")),
    GateCheck("P2", "managed cost report RPC", "supabase/migrations/20260514_p2_cost_report_rpc.sql", ("get_cost_report", "SECURITY DEFINER")),
    GateCheck("P2", "prompt fuzz security tests", "nexus_backend/tests/security/test_fuzz_api.py", ("@given", "prompt")),
    # P3-P6: sustained production quality controls.
    GateCheck("P3", "Supabase client import is chunk-stable", "src/lib/httpClient.ts", ("import { supabase }", "supabase.auth.getSession")),
    GateCheck("P3", "bundle budget script", "scripts/check_bundle_budget.mjs", ("maxJsChunkBytes", "vendor-jspdf-", "vendor-html2canvas-")),
    GateCheck("P4", "bundle budget package command", "package.json", ('"check:bundle"', "check_bundle_budget.mjs")),
    GateCheck("P4", "bundle budget wired to CI", ".github/workflows/ci.yml", ("Check bundle budget", "npm run check:bundle")),
    GateCheck("P5", "private deployment doctor", "scripts/private_deploy_doctor.py", ("--env", "PRIVATE_DEPLOYMENT", "CORS_ORIGINS")),
    GateCheck("P6", "release evidence collector", "scripts/collect_release_evidence.py", ("release-evidence.json", "sha256", "<redacted>")),
    GateCheck("P1", "private PgBouncer guidance", "docs/PRIVATE_DEPLOYMENT_PGBOUNCER.md", ("pool_mode", "SUPABASE_DB_POOLER_URL", "/health/ready")),
    GateCheck("P1", "small-company load profile", "nexus_backend/tests/k6/small_company.js", ("small_company_20_50_users", "p(95)<900")),
    GateCheck("P1", "nightly agent replay runner", "scripts/agent_replay_nightly.py", ("AGENT_REPLAY_BASE_URL", "promote-failures")),
    GateCheck("P1", "nightly agent quality workflow", ".github/workflows/nightly-agent-quality.yml", ("schedule:", "agent_replay_nightly.py")),
    GateCheck("P1", "SOC2 evidence collector", "scripts/collect_soc2_evidence.py", ("CC6_logical_access", "CC7_security_monitoring")),
    GateCheck("P1", "rate limiter production fail-closed", "nexus_backend/app/core/rate_limiter.py", ("_redis_is_required", "backend_unavailable")),
    GateCheck("P0", "stream lifecycle split", "nexus_backend/app/agent/stream.py", ("stream_lifecycle", "emit_error_and_cleanup", "cleanup_on_disconnect", "ThinkTagTracker")),
    GateCheck("P1", "stream event helpers", "nexus_backend/app/agent/stream_events.py", ("process_stream_event", "ThinkTagTracker")),
    GateCheck("P0", "gateway get_llm fail-closed", "nexus_backend/app/services/llm_gateway/__init__.py", ("requires resolved_config", "Use await resolve_model_config")),
    GateCheck("P1", "standard health probes", "nexus_backend/app/main.py", ('"/health/live"', '"/health/ready"')),
    GateCheck("P1", "web vitals backend route", "nexus_backend/app/routers/metrics.py", ("/web-vitals", "/slo")),
    GateCheck("P2", "single theme context adapter", "src/contexts/ThemeContext.tsx", ("useEnhancedTheme", "return <>{children}</>")),
    GateCheck("P2", "SLO dashboard route", "src/routes/adminRoutes.tsx", ('path="slo"', "SLODashboard")),
    GateCheck("P2", "deployment readiness center", "src/pages/DeploymentReadinessPage.tsx", ("上线交付中心", "/api/system/deployment-health", "ACCEPTANCE_COMMANDS")),
    GateCheck("P2", "deployment readiness route", "src/routes/adminRoutes.tsx", ('path="deployment-readiness"', "DeploymentReadinessPage")),
    GateCheck("P2", "first-week launch checklist", "src/components/product/LaunchChecklistPanel.tsx", ("首周落地任务", "nexus:first-week-launch-checklist")),
    GateCheck("P2", "customer success dashboard", "src/pages/CustomerSuccessPage.tsx", ("客户成功看板", "首周激活目标")),
    GateCheck("P2", "permission matrix page", "src/pages/PermissionMatrixPage.tsx", ("权限与 AI 安全矩阵", "Tool RBAC")),
    GateCheck("P2", "AI operation transparency", "src/components/ai/genui/ReasoningTrace.tsx", ("AI 操作透明度", "HITL/RBAC")),
    GateCheck("P0", "small-company launch profile", "src/config/featureFlags.ts", ("SMALL_COMPANY_LAUNCH_MODULES", "VITE_LAUNCH_PROFILE", "EXTENDED_LAUNCH_MODULES")),
    GateCheck("P0", "customer acceptance gate", "scripts/customer_acceptance_gate.py", ("SMALL_COMPANY_MODULES", "Tool RBAC", "Irreversible HITL")),
    GateCheck("P0", "customer business acceptance E2E", "e2e/customer-business-acceptance.spec.ts", ("CRM can create a customer", "AI chat sends a message", "employee role is blocked")),
    GateCheck("P1", "customer handoff generator", "scripts/generate_customer_handoff.py", ("customer-handoff.md", "Required Acceptance Commands", "small_company")),
    GateCheck("P1", "customer acceptance criteria", "docs/CUSTOMER_ACCEPTANCE_CRITERIA.md", ("Default Launch Profile", "Acceptance Rules", "customer-business-acceptance.spec.ts")),
]


def main() -> int:
    failures: list[str] = []
    warnings: list[str] = []
    print("Release quality gate: P0-P6 static controls")
    for check in CHECKS:
        ok, reason = run_check(check)
        status = "OK" if ok else ("WARN" if check.severity == "warning" else "FAIL")
        print(f"{status:<4} [{check.level}] {check.name}")
        if ok:
            continue
        message = f"[{check.level}] {check.name}: {reason}"
        if check.severity == "warning":
            warnings.append(message)
        else:
            failures.append(message)

    print("")
    print(f"Summary: {len(failures)} critical failure(s), {len(warnings)} warning(s).")
    if failures:
        for item in failures:
            print(f" - {item}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
