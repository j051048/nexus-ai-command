import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reconcile_migration_history import extract_contract


def test_extract_contract_finds_created_tables_and_added_columns(tmp_path: Path):
    migration = tmp_path / "20260101_contract.sql"
    migration.write_text(
        """
        CREATE TABLE IF NOT EXISTS public.widgets (id uuid PRIMARY KEY);
        ALTER TABLE public.widgets
          ADD COLUMN IF NOT EXISTS status text,
          ADD COLUMN score integer;
        """,
        encoding="utf-8",
    )
    contract = extract_contract(migration)
    assert contract.tables == ("widgets",)
    assert contract.columns == {"widgets": ("score", "status")}
    assert len(contract.checksum) == 64


def test_extract_contract_skips_history_table_as_proof(tmp_path: Path):
    migration = tmp_path / "20260102_metadata.sql"
    migration.write_text(
        "CREATE TABLE IF NOT EXISTS public.migration_history (id bigint);",
        encoding="utf-8",
    )
    assert extract_contract(migration).verifiable is False


def test_reconciliation_backfills_blank_checksums_but_rejects_real_drift():
    sql = (ROOT / "supabase/migrations/20260810_003_operational_closure.sql").read_text(
        encoding="utf-8"
    )

    assert "COALESCE(existing_checksum, '') <> ''" in sql
    assert "existing_checksum <> p_checksum" in sql
    assert "WHERE public.migration_history.checksum = ''" in sql
