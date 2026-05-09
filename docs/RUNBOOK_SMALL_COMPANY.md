# Small Company Production Runbook

This runbook is for the first 20-50 employee deployment.

## Daily checks

1. Open `/api/system/deployment-health` as an admin and confirm `ready=true`.
2. Check Sentry for new 5xx, auth, billing, and approval errors.
3. Check LLM cost dashboard for daily tenant spend and abnormal token spikes.
4. Confirm Redis is healthy. Redis failure must block token budgets in production instead of falling back to memory.
5. Confirm the latest database backup exists.

## Weekly checks

1. Restore the latest backup into staging.
2. Run the 10-flow smoke test:
   login, chat, CRM, document upload, knowledge query, approval, work order, finance, report, billing.
3. Review newly opened module usage and disable any module that repeatedly fails smoke testing.
4. Rotate API keys if any integration logs show suspicious failures.
5. Review top failed tools and add friendly error mappings.

## Incident response

1. AI provider outage:
   set `AI_FALLBACK_API_KEY` and `AI_FALLBACK_BASE_URL`, or route to the mini model until the primary recovers.

2. Cost spike:
   lower `MAX_CONCURRENT_LLM_PER_TENANT`, `TOKEN_BUDGET_MAX_COST_PER_DAY_PER_TENANT`, and `LLM_MAX_COST_PER_REQUEST`.
   Use the cost dashboard to identify the tenant and user.

3. Redis outage:
   keep production fail-closed for token budgets.
   Do not set `TOKEN_BUDGET_MEMORY_FALLBACK_ENABLED=true` in production.

4. Supabase/RLS concern:
   disable new user invites, export audit logs, verify the affected organization ID, then restore from backup if data integrity is compromised.

5. Frontend broken chunk:
   redeploy the latest known good build. The app already has lazy chunk retry, but a bad deployment still requires rollback.

## Backup

Linux/macOS:

```bash
DATABASE_URL="postgresql://..." ./scripts/backup_supabase.sh
```

Windows PowerShell:

```powershell
$env:DATABASE_URL="postgresql://..."
.\scripts\backup_supabase.ps1
```

## Restore drill

1. Create a staging database.
2. Restore with `pg_restore --clean --if-exists --no-owner --dbname "$DATABASE_URL" backups/nexus-full-YYYYMMDD-HHMMSS.dump`.
3. Apply any newer migrations.
4. Run login, chat, CRM, document, approval, and billing smoke tests.

## Module rollout policy

Default enabled for first customer launch:
`approval`, `assets`, `battlecards`, `billing`, `certificates`, `crm`, `custom_dashboard`, `documents`, `finance`, `form_designer`, `hr`, `import`, `inventory`, `knowledge`, `oa`, `plugins`, `projects`, `report_builder`, `reports`, `sales`, `soul_document`, `tender`, `training`, `vmd`, `workflow_designer`, `work_orders`.

Keep disabled:
`dev_tools`.

Integration modules are usable only after their production credentials are configured. For Kingdee-backed flows, set `KINGDEE_BASE_URL` and `KINGDEE_API_KEY`; otherwise the API will return a controlled integration error.
