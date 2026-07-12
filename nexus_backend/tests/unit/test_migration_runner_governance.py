from pathlib import Path

import pytest

from app.core import migration_runner


def test_runtime_runner_uses_canonical_migration_directory():
    assert migration_runner.MIGRATIONS_DIR.name == "migrations"
    assert migration_runner.MIGRATIONS_DIR.parent.name == "supabase"
    assert migration_runner.migration_files()


def test_migration_checksum_is_stable(tmp_path: Path):
    migration = tmp_path / "20260712_example.sql"
    migration.write_text("select 1;\n", encoding="utf-8")
    first = migration_runner.migration_checksum(migration)
    assert first == migration_runner.migration_checksum(migration)
    migration.write_text("select 2;\n", encoding="utf-8")
    assert first != migration_runner.migration_checksum(migration)


def test_applied_checksum_drift_fails_closed(monkeypatch, tmp_path: Path):
    migration = tmp_path / "20260712_example.sql"
    migration.write_text("select 1;\n", encoding="utf-8")
    monkeypatch.setattr(migration_runner, "migration_files", lambda: [migration])
    with pytest.raises(RuntimeError, match="checksum drift"):
        migration_runner.validate_applied_checksums({migration.name: "wrong"})
