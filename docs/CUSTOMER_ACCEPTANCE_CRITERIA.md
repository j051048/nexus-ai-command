# Small Company Customer Acceptance Criteria

This is the default first-launch scope for 20-50 person deployments. Extended modules can be enabled after the customer has accepted the core operating loop.

## Default Launch Profile

`VITE_LAUNCH_PROFILE=small_company`

Required modules:

- CRM
- Approval
- Documents
- Knowledge
- Finance
- HR
- OA
- Projects
- Reports
- VMD
- Plugins
- Workflow Designer

## Acceptance Rules

1. Each required module has a frontend route and a smoke path in `src/config/customerLaunchModules.ts`.
2. Each required module is covered by `e2e/top10-critical-flows.spec.ts` or a module-specific E2E suite.
3. The first-launch business loop is covered by `e2e/customer-business-acceptance.spec.ts`: login, CRM, approval, documents, projects, HR/OA, AI chat, and role blocking.
4. AI write operations must pass through Tool RBAC, idempotency, audit logging, and HITL confirmation for irreversible actions.
5. Deployment evidence must include release quality gate output, RLS scanner output, production readiness output, live health-check output, bundle budget output, release evidence manifest, and SOC2 evidence manifest.
6. Customer handoff must include enabled modules, deployment health checks, backup/restore instructions, Agent replay posture, and known optional integrations.
7. A 20-50 person pilot load run should pass `nexus_backend/tests/k6/small_company.js` before customer sign-off.
8. The admin-facing launch handoff must be visible in `/deployment-readiness` for boss/founder roles.
9. The first-week adoption checklist must be visible from the boss and employee dashboards so the customer can self-validate CRM, approval, documents, and AI Q&A.
10. The customer success dashboard must expose first-week activation, approval acceleration, AI usage, and boss review goals.
11. The permission and AI safety matrix must be available to customer admins and explain RLS, Tool RBAC, HITL, prompt defense, budget breakers, and audit logs.
12. AI reasoning trace UI must explain which operational facts are visible to users and which internal reasoning remains hidden.

## Exit Criteria

- `python scripts/customer_acceptance_gate.py` passes.
- `python scripts/release_quality_gate.py` passes.
- `node scripts/production_readiness_check.mjs --env .env.production` passes with customer secrets configured.
- `node scripts/production_health_check.mjs --base-url https://YOUR-BACKEND-DOMAIN` passes after deployment.
- `python scripts/collect_soc2_evidence.py` passes and writes `dist/soc2-evidence.json`.
- `python scripts/agent_replay_nightly.py` passes in static mode or promotes failures when replay credentials are configured.
- `npm run build` and `npm run check:bundle` pass.
- Top critical Playwright smoke suite passes for the customer module set.
- Customer business acceptance suite passes: `npm run test:e2e -- e2e/customer-business-acceptance.spec.ts --project=chromium`.
- Boss/employee dashboards show the first-week checklist, `/customer-success` is accessible to managers, and `/permissions-matrix` is accessible to founders/bosses.
