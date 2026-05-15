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
3. AI write operations must pass through Tool RBAC, idempotency, audit logging, and HITL confirmation for irreversible actions.
4. Deployment evidence must include release quality gate output, RLS scanner output, production readiness output, bundle budget output, and release evidence manifest.
5. Customer handoff must include enabled modules, deployment health checks, backup/restore instructions, and known optional integrations.

## Exit Criteria

- `python scripts/customer_acceptance_gate.py` passes.
- `python scripts/release_quality_gate.py` passes.
- `node scripts/production_readiness_check.mjs --env .env.production` passes with customer secrets configured.
- `npm run build` and `npm run check:bundle` pass.
- Top critical Playwright smoke suite passes for the customer module set.
