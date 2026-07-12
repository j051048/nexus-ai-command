"""Static migration governance gate used by local checks and CI."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
RUNNER = ROOT / "nexus_backend" / "app" / "core" / "migration_runner.py"
NAME_PATTERN = re.compile(r"^\d{8}[A-Za-z0-9_.-]*\.sql$")


def main() -> int:
    failures: list[str] = []
    files = sorted(MIGRATIONS.glob("*.sql"))
    executable = [path for path in files if path.name[:8].isdigit()]
    invalid = [
        path.name for path in executable if not NAME_PATTERN.fullmatch(path.name)
    ]
    duplicates = [
        name for name, count in Counter(p.name for p in executable).items() if count > 1
    ]

    if not files:
        failures.append("canonical supabase/migrations directory is empty")
    if invalid:
        failures.append("invalid migration names: " + ", ".join(invalid))
    if duplicates:
        failures.append("duplicate migration names: " + ", ".join(duplicates))

    runner = RUNNER.read_text(encoding="utf-8")
    required = (
        'REPOSITORY_ROOT / "supabase" / "migrations"',
        "validate_applied_checksums",
        "migration_checksum",
    )
    for token in required:
        if token not in runner:
            failures.append(f"runtime migration runner missing: {token}")
    if "supabase_migrations" in runner:
        failures.append("runtime migration runner still references a legacy directory")

    replay = (ROOT / "scripts" / "verify_migration_replay.py").read_text(
        encoding="utf-8"
    )
    if "MIGRATION_PATTERN.fullmatch" not in replay:
        failures.append(
            "scratch replay does not use the canonical executable-file filter"
        )

    print(f"Migration governance: {len(executable)} executable files")
    if failures:
        print("MIGRATION_GOVERNANCE_FAIL")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("MIGRATION_GOVERNANCE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
