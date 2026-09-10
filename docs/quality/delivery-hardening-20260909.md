# Delivery Hardening: 2026-09-09

Scope: customer proposals, tender responses and research briefs. Preserve the
existing Agent, model selection, CRM, knowledge permissions and approval gates.

| Priority | Work | Status |
| --- | --- | --- |
| P0 | Executable requirements and catalog-backed budget checks | Implemented; focused tests pass |
| P0 | Diverse, complete, permission-scoped evidence selection | Implemented; long-document and ACL tests pass |
| P0 | Actual exported-file acceptance and synthetic regression corpus | Implemented; synthetic cases are not customer acceptance |
| P1 | Lease-guarded generation checkpoints and safe recovery | Implemented; database deployment and live recovery remain to verify |
| P1 | Result preview, format selection and revision workflow | Implemented; desktop/mobile/resize browser tests pass |
| P1 | Artifact-level usage and recovery accounting | Implemented; retained-stage accounting, not billing |
| P2 | Reviewed feedback and reproducible release evidence | Implemented; authorized customer reviews still required |
| P2 | Handover documentation and regression verification | Updated; live acceptance remains separate |

Customer blind reviews, live model quality, visual review in Word/PDF readers,
production migrations and load tests are separate acceptance activities. Synthetic
fixtures are not real customer proof. No numerical product score is claimed.

## 2026-09-10 CI repair

- `artifact_stage_checkpoints` already had RLS enabled and client-role privileges
  revoked, but had no explicit policy. The static coverage gate correctly reported
  `MISSING_POLICY`; it did not demonstrate a public data leak.
- Apply `supabase/migrations/20260910_001_artifact_stage_checkpoint_policy.sql`
  after `20260909_001_artifact_stage_checkpoints.sql`. Do not edit the previous
  migration or bypass checksum verification on an existing database.
- The new policy is `FOR ALL TO service_role` only. `PUBLIC`, `anon` and
  `authenticated` have no table privileges. The worker RPC still verifies the
  organization membership, job creator, job state and current lease. A service
  role may bypass RLS; this policy is not a substitute for those RPC checks.
- The matching rollback under `supabase/migrations/rollback/` removes only this policy,
  preserving the table, RLS and revoked client access. Rolling it back intentionally
  returns to the prior missing-policy state; prefer roll-forward for deployment.
- `Index.tsx` now owns a persistent `DeliverableWorkspace`. Desktop and mobile
  headers render its trigger without owning the document dialog. Resizing retains
  open previews, unsent revisions and selected file formats; changing account or
  tenant remounts the workspace and clears sensitive state.
- The former mobile E2E opened at desktop width then changed the viewport. It
  exposed a real layout-remount bug. Coverage now includes initial desktop,
  initial mobile, both resize directions, revision submission and focus restoration.

Local regression commands (use the backend Python 3.11 environment):

```text
python scripts/scan_rls_coverage.py
python scripts/scan_rls_policy_columns.py
python scripts/check_migration_governance.py
python scripts/generate_handover_inventory.py
python scripts/check_handover_readiness.py
npx playwright test e2e/artifact-delivery-workspace.spec.ts --project=chromium --retries=0
npm run quality:frontend
```

The RLS scan is static, not an execution against a deployed database. These local
checks do not apply the migration; database deployment is a separate operation.

Verification on the local Windows checkout:

- RLS coverage: 135 tenant tables, zero missing RLS/policies; policy-column,
  schema-conflict and migration-governance checks passed.
- Delivery-focused backend regression: 90 passed. Black (24.10.0), Ruff and
  handover checks passed. This is not a full backend-suite certification: the
  earlier full Windows run hit a native Python crash; Linux CI still needs to
  establish that result.
- Frontend component regression: 19 passed. Full Chromium suite without retries:
  63 passed, 17 conditionally skipped, zero failures. Existing credential-dependent
  and opt-in visual tests were not changed to bypass their requirements.
- TypeScript diagnostic comparison against pre-repair HEAD: 114 existing errors,
  114 after this repair, zero newly introduced diagnostics. Do not report full
  type-check success or relax its configuration to hide this debt.

## Implementation boundaries for handover

- Requirements live in `app/agent/delivery_requirements.py`; evaluation and
  tenant price-book resolution live in `app/services/delivery_requirement_service.py`.
  Required phrases and local citations provide deterministic coverage, not proof
  of semantic entailment. Semantic review and human approval remain necessary.
- Evidence compilation scans beyond the beginning of a document, while final
  context selection remains bounded. Preview and download recheck current source
  permissions and versions in `artifact_workspace_service.py`.
- Stage checkpoints cache successful analysis, strategy, section generation and
  targeted rewrites. Editorial synthesis and quality checks still run. Inputs,
  source snapshots and pipeline/template versions contribute to invalidation.
  Seven days is the reuse TTL, not automatic deletion: stored payloads remain until
  the job is deleted or a separate retention process removes them. Agree and
  implement retention before production rollout.
- Revisions create a separate artifact linked by `revision_of`, preserving the
  original. They do not overwrite it or inherit approval. Failed quality checks
  continue to label downloads as review drafts.
- Usage includes retained successful stages, not every failed/retried provider
  call. Missing cost stays unknown. Do not use this report as an invoice ledger.
- `scripts/evaluate_delivery_release.py` validates actual DOCX/PDF/XLSX bytes.
  Its manifest requires provenance (`git_commit`, `pipeline_version`, `model`,
  `template_version`, `dataset_version`) and cases with `id`, `file`, `title`,
  `required_terms` and `minimum_characters`. Files must remain under the manifest
  directory. Keep customer files and reports outside the repository.
- `--require-customer-proof` additionally requires at least 25 cases covering the
  five instrument families, customer authorization references and human reviews
  tied to each file's SHA-256. These are reviewer attestations, not independent
  verification of customer consent. Synthetic fixtures cannot satisfy this mode.
