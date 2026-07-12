"""Replay all Supabase SQL migrations against an opt-in scratch database.

By default this is a no-op so CI can keep the gate wired before a disposable
database secret is configured. Set MIGRATION_REPLAY_DATABASE_URL or pass
--database-url to run the real replay. The target database must be disposable.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"
MIGRATION_PATTERN = re.compile(r"^\d{8}[A-Za-z0-9_.-]*\.sql$")


def _database_url(cli_value: str | None) -> str | None:
    return (
        cli_value
        or os.getenv("MIGRATION_REPLAY_DATABASE_URL")
        or os.getenv("SUPABASE_MIGRATION_REPLAY_DB_URL")
    )


def _psql() -> str | None:
    return os.getenv("PSQL_BIN") or shutil.which("psql")


def _migration_files() -> list[Path]:
    return sorted(
        path
        for path in MIGRATIONS_DIR.glob("*.sql")
        if MIGRATION_PATTERN.fullmatch(path.name)
    )


def replay(database_url: str, psql_bin: str) -> tuple[bool, str]:
    for path in _migration_files():
        result = subprocess.run(
            [
                psql_bin,
                database_url,
                "--set",
                "ON_ERROR_STOP=1",
                "--file",
                str(path),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            return False, f"{path.name} failed:\n{detail}"
    return True, f"replayed {len(_migration_files())} migrations"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url")
    parser.add_argument("--require-db", action="store_true")
    args = parser.parse_args()

    database_url = _database_url(args.database_url)
    if not database_url:
        message = "MIGRATION_REPLAY_DATABASE_URL is not set"
        if args.require_db:
            print(f"ERROR: {message}", file=sys.stderr)
            return 1
        print(f"SKIP: {message}")
        return 0

    psql_bin = _psql()
    if not psql_bin:
        message = "psql is not installed or PSQL_BIN is not set"
        if args.require_db:
            print(f"ERROR: {message}", file=sys.stderr)
            return 1
        print(f"SKIP: {message}")
        return 0

    ok, message = replay(database_url, psql_bin)
    if not ok:
        print("Migration replay failed", file=sys.stderr)
        print(message, file=sys.stderr)
        return 1
    print(f"OK: {message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
