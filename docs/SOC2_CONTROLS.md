# SOC2 Controls Map

This document is the code-linked control map for a Type I readiness package. It is not a substitute for an auditor, but it gives implementation, evidence, and owner boundaries for the controls that matter before enterprise pilots.

## Scope

- Product: Nexus AI Command multi-tenant SaaS and private deployment package.
- Systems: FastAPI backend, React frontend, Supabase/PostgreSQL, Redis/Celery, LLM Gateway, audit and compliance APIs.
- Data: tenant business data, user identity data, LLM prompts/responses, tool execution records, billing and usage records.

## Control Matrix

| Criteria | Control | Code Evidence | Runtime Evidence |
| --- | --- | --- | --- |
| CC1 | Security ownership and release accountability are documented. | `src/config/customerLaunchModules.ts`, `docs/PRODUCTION_LAUNCH_CHECKLIST.md` | Signed launch checklist per customer deployment. |
| CC2 | Security changes are communicated through CI and deployment runbooks. | `.github/workflows/ci.yml`, `scripts/release_quality_gate.py` | CI run logs and deployment ticket links. |
| CC3 | Product risks are assessed before launch. | `scripts/production_readiness_check.mjs`, `scripts/private_deploy_doctor.py` | Readiness report attached to the deployment record. |
| CC5 | Controls are enforced by automated tests and guardrails. | `nexus_backend/tests/unit/test_architecture_guards.py`, `scripts/scan_rls_coverage.py` | Passing CI artifacts and RLS scan output. |
| CC6 | Logical access is role based and tenant scoped. | `nexus_backend/app/core/auth.py`, `nexus_backend/app/core/api_key_middleware.py`, `nexus_backend/app/core/tool_rbac.py`, `nexus_backend/app/services/permission_service.py` | Access review export and failed-auth logs. |
| CC6 | Enterprise SSO supports controlled identity provider onboarding. | `nexus_backend/app/routers/enterprise_sso.py`, `nexus_backend/app/services/enterprise_sso_service.py` | IdP metadata, SSO test login, signed-state verification. |
| CC7 | Security events are logged and reviewed. | `nexus_backend/app/core/audit_logger.py`, `nexus_backend/app/routers/compliance.py`, `supabase/migrations/20260419_p1_audit_logs_immutable.sql` | Immutable audit export and incident review notes. |
| CC7 | Prompt injection and data exfiltration paths are tested. | `nexus_backend/app/core/prompt_firewall.py`, `nexus_backend/tests/security/test_fuzz_api.py` | Security test output and blocked-request samples. |
| CC8 | Changes to schema and security posture are version controlled. | `supabase/migrations/`, `scripts/scan_rls_coverage.py` | Migration deployment logs and schema diff approval. |
| CC9 | Vendor and model risk is governed by routing, budgets, and fallbacks. | `nexus_backend/app/services/llm_gateway/`, `nexus_backend/app/services/token_service.py`, `supabase/migrations/20260514_p2_cost_report_rpc.sql` | Tenant cost report, model fallback incidents, monthly budget alerts. |

## Evidence Collection

For each production or private deployment, store these artifacts in the customer handoff folder:

1. `npm run build` output.
2. Backend guardrail test output.
3. `python scripts/scan_rls_coverage.py` output.
4. `python scripts/release_quality_gate.py` output.
5. `node scripts/production_readiness_check.mjs --env .env.production` output with secrets redacted.
6. Audit export sample from `/api/compliance/audit/export`.
7. SSO smoke test result when enterprise SSO is enabled.
8. Backup and restore drill result for the customer database.

## Open Auditor Follow-Ups

- Type II requires at least a multi-month evidence window; this repository only supplies Type I implementation evidence.
- SAML XML signature verification should be validated against each customer IdP metadata file during onboarding.
- Private deployments must document customer-owned infrastructure responsibility boundaries.
