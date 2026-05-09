# Nexus AI Command Production Launch Checklist

This checklist targets the first real rollout for a 20-50 person company.

## P0: Must pass before opening the app

1. Configure production secrets from `.env.production.example`.
   Required: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET` or `JWT_SECRET`, `REDIS_URL`, `OPENAI_API_KEY`, `AI_BASE_URL`, `ENCRYPTION_KEY`, `HEALTH_CHECK_TOKEN`.

2. Use durable Agent state.
   Set `LANGGRAPH_CHECKPOINTER=postgres`. Do not use memory checkpointer in production.

3. Keep cost blast radius small.
   Recommended first-launch limits:
   `MAX_CONCURRENT_LLM_PER_TENANT=5`,
   `TOKEN_BUDGET_MAX_COST_PER_DAY_PER_TENANT=80`,
   `TOKEN_BUDGET_MAX_COST_PER_MONTH_PER_TENANT=1500`,
   `LLM_MAX_COST_PER_REQUEST=1.2`.

4. Run all Supabase migrations.
   The launch feature flags migration must exist and be applied:
   `supabase/migrations/20260508_launch_readiness_feature_flags.sql`.

5. Enable the customer-facing launch modules and keep developer tools closed.
   Default customer launch modules:
   `approval,assets,battlecards,billing,certificates,crm,custom_dashboard,documents,finance,form_designer,hr,import,inventory,knowledge,oa,plugins,projects,report_builder,reports,sales,soul_document,tender,training,vmd,workflow_designer,work_orders`.
   Keep only `dev_tools` disabled unless a named admin explicitly needs it in staging.

6. Configure real external credentials before demonstrating integration workflows.
   For Kingdee-backed flows, set `KINGDEE_BASE_URL` and `KINGDEE_API_KEY`; otherwise the integration endpoints fail closed instead of returning mock data.

7. Lock down CORS.
   `CORS_ORIGINS` must list exact production app domains. Do not use `*`.

8. Verify health endpoints.
   Public: `/health`.
   Private: `/health/deep` with `X-Health-Token`.
   Admin readiness: `/api/system/deployment-health`.

9. Run local production readiness check.
   ```bash
   npm run check:prod -- --env .env.production
   ```

10. Run frontend build.
   ```bash
   npm run build
   ```

11. Run core backend hardening tests.
    ```bash
    python -m pytest nexus_backend/tests/unit/test_p1_hardening.py -q -o addopts=''
    ```

## P1: Must complete during the first customer week

1. Configure Sentry before inviting real users.
   Use alerts for 5xx bursts, auth failures, and payment errors.

2. Configure Langfuse or equivalent LLM tracing.
   Use `LANGFUSE_SAMPLE_RATE=0.2` for first launch unless debugging an incident.

3. Create daily database backups.
   Linux/macOS: `scripts/backup_supabase.sh`.
   Windows: `scripts/backup_supabase.ps1`.

4. Create a restore drill.
   Restore one backup into a staging Supabase project and verify login, CRM, chat, documents, approvals.

5. Review newly opened customer modules with the customer champion.
   Plugin marketplace, workflow designer, form designer, VMD, tender, training, HR, inventory, assets, and certificates should be exercised with real tenant data before broad rollout.

6. Review cost dashboard every day.
   Watch top users, top tenants, model mix, fallback rate, failed tool calls, and token budget denials.

7. Run a 10-flow smoke test after every deployment.
   Login, chat, CRM create/update, document upload/query, approval submit/approve, work order create, finance view, report view, billing page, logout.
