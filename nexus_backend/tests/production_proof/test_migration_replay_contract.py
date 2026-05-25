from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"


def test_migration_replay_has_ordered_sql_files():
    migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
    assert len(migrations) >= 100
    assert all(path.name[:8].isdigit() for path in migrations[:20])


def test_agent_evolution_migration_does_not_redefine_eval_cases():
    migration = MIGRATIONS_DIR / "20260525_agent_evolution_ops.sql"
    content = migration.read_text(encoding="utf-8")
    for table in [
        "agent_prompt_versions",
        "agent_improvement_proposals",
        "agent_ci_runs",
        "agent_reward_events",
        "agent_skill_marketplace",
        "agent_redteam_findings",
        "agent_trust_reports",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS public.{table}" in content
    assert "CREATE TABLE IF NOT EXISTS public.agent_eval_cases" not in content
    assert "agent_eval_cases is intentionally not created here" in content


def test_agent_eval_cases_reconcile_migration_handles_legacy_schema():
    migration = MIGRATIONS_DIR / "20260525_agent_eval_cases_schema_reconcile.sql"
    content = migration.read_text(encoding="utf-8")
    for token in [
        "ADD COLUMN IF NOT EXISTS organization_id",
        "column_name = 'org_id'",
        "column_name = 'criticality'",
        "column_name = 'query'",
        "schema-conflict-scan: allow-reconcile-create",
        "idx_agent_eval_cases_source_unique",
        "agent_eval_cases_tenant_read",
        "agent_eval_cases_tenant_write",
    ]:
        assert token in content


def test_agent_eval_cases_rls_uses_canonical_tenant_column():
    migration = MIGRATIONS_DIR / "20260514_p0_tenant_rls_policy_backfill.sql"
    content = migration.read_text(encoding="utf-8")
    policy_start = content.index("CREATE POLICY p0_agent_eval_cases_tenant_isolation")
    policy_end = content.index(
        "DROP POLICY IF EXISTS p0_agent_failure_logs_tenant_isolation",
        policy_start,
    )
    policy = content[policy_start:policy_end]
    assert "organization_id::text = public.current_tenant_id_text()" in policy
    assert "org_id::text = public.current_tenant_id_text()" not in policy


def test_hr_rls_and_indexes_use_canonical_tenant_column():
    rls_migration = (
        MIGRATIONS_DIR / "20260514_p0_tenant_rls_policy_backfill.sql"
    ).read_text(encoding="utf-8")
    index_migration = (MIGRATIONS_DIR / "20260405_p03_performance_indexes.sql").read_text(
        encoding="utf-8"
    )
    assert "p0_hr_performance_reviews_tenant_isolation" in rls_migration
    assert "p0_hr_salary_records_tenant_isolation" in rls_migration
    assert "hr_performance_reviews FOR ALL USING (organization_id::text" in rls_migration
    assert "hr_salary_records FOR ALL USING (organization_id::text" in rls_migration
    assert "hr_performance_reviews(org_id)" not in index_migration
    assert "hr_salary_records(org_id)" not in index_migration


def test_staging_migration_verifier_exists():
    verifier = ROOT / "scripts" / "verify_staging_migrations.py"
    content = verifier.read_text(encoding="utf-8")
    assert "--require-db" in content
    assert "RLS" in content or "rls" in content


def test_migration_schema_conflict_scanner_exists():
    scanner = ROOT / "scripts" / "scan_migration_schema_conflicts.py"
    content = scanner.read_text(encoding="utf-8")
    assert "schema-compatible" in content
    assert "ALLOW_RECONCILE_CREATE" in content
    assert "extract_definitions" in content
    assert "CREATE_RE" in content


def test_rls_policy_column_scanner_exists():
    scanner = ROOT / "scripts" / "scan_rls_policy_columns.py"
    content = scanner.read_text(encoding="utf-8")
    assert "TENANT_COLUMN_RE" in content
    assert "current_tenant_id_text" in content
    assert "is not defined" in content


def test_scratch_migration_replay_command_exists():
    replay = ROOT / "scripts" / "verify_migration_replay.py"
    content = replay.read_text(encoding="utf-8")
    assert "MIGRATION_REPLAY_DATABASE_URL" in content
    assert "ON_ERROR_STOP=1" in content
    assert "--require-db" in content


def test_local_python_launcher_exists():
    launcher = ROOT / "scripts" / "dev_python.ps1"
    content = launcher.read_text(encoding="utf-8")
    assert ".venv" in content
    assert "trying global Python" in content
    assert "No Python runtime found" in content
