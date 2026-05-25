# Production Proof Plan

This plan converts the audit findings into executable proof layers. Static
architecture guards remain useful, but they are no longer treated as proof that
business flows actually run.

## Proof Layers

1. Golden business flows
   - Manifest: `nexus_backend/tests/production_proof/fixtures/golden_business_flows.json`
   - Offline check: `pytest nexus_backend/tests/production_proof/test_golden_business_flows.py`
   - Real mode: `RUN_REAL_GOLDEN_FLOWS=1`

2. Agent graph E2E
   - Contract: `test_agent_graph_e2e_contract.py`
   - Real mode: `RUN_REAL_AGENT_GRAPH_E2E=1`
   - Required proof: user message -> `graph.ainvoke()` -> tool calls -> persisted output.

3. Tenant isolation / RLS
   - Contract: `test_tenant_rls_isolation_contract.py`
   - Real mode: `RUN_REAL_RLS_PROOF=1`
   - Required proof: Org A cannot read or mutate Org B data.

4. Intent classifier baseline
   - Dataset: `fixtures/intent_baseline.json`
   - CI threshold: 90% minimum deterministic baseline.
   - Next step: replace deterministic helper with real router once stable.

5. Tool error matrix
   - Contract: `test_tool_error_matrix_contract.py`
   - Required cases per core tool: success, invalid params, permission denied, timeout.

6. Migration replay
   - Contract: `test_migration_replay_contract.py`
   - Staging verifier: `scripts/verify_staging_migrations.py --require-db`
   - Conflict scanner: `scripts/scan_migration_schema_conflicts.py`
   - RLS policy column scanner: `scripts/scan_rls_policy_columns.py`
   - Scratch replay command: `scripts/verify_migration_replay.py --require-db`
   - Required proof: empty DB can apply all migrations.
   - Required guard: duplicate `CREATE TABLE IF NOT EXISTS` definitions must
     be schema-compatible; otherwise add a reconcile migration instead.
   - Required guard: tenant policies that use `current_tenant_id_text()` must
     reference columns that exist in the target table.

7. SSE disconnect and resume
   - Contract: `test_sse_reconnect_contract.py`
   - Required proof: disconnect detection, idempotent resume, no duplicate message,
     final state reconciled.

8. API client unification
   - Contract: `test_api_client_and_transaction_contract.py`
   - Required proof: secondary clients delegate to `httpClient`.

9. Transaction / RPC boundary
   - Contract: `test_api_client_and_transaction_contract.py`
   - Required proof: complex business operations use transactional RPC or a documented
     atomic boundary.

10. Load and capacity
   - Contract: `test_load_and_capacity_contract.py`
   - Profiles: `nexus_backend/tests/k6/baseline.js`, `small_company.js`
   - Required proof: `/api/chat` and core AI endpoints have capacity baseline.

11. LLM VCR replay
   - Cassette: `fixtures/llm_replay_cassette.json`
   - Required proof: prompt/model changes can be replayed without live LLM access.

12. CI production proof wiring
   - Gate: `scripts/production_proof_gate.py`
   - CI: `.github/workflows/ci.yml`
   - Required proof: this suite runs on every backend CI pass.

## Recommended Commands

```bash
python scripts/production_proof_gate.py
python scripts/scan_rls_policy_columns.py
python scripts/verify_migration_replay.py
cd nexus_backend
pytest tests/production_proof -q
```

For real staging proof:

```bash
RUN_REAL_GOLDEN_FLOWS=1 \
RUN_REAL_AGENT_GRAPH_E2E=1 \
RUN_REAL_RLS_PROOF=1 \
TEST_SUPABASE_URL=... \
TEST_SUPABASE_SERVICE_KEY=... \
TEST_SUPABASE_ANON_KEY=... \
MIGRATION_REPLAY_DATABASE_URL=... \
TEST_LLM_RECORDING_MODE=replay \
pytest nexus_backend/tests/production_proof -q
```
