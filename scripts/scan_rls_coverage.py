#!/usr/bin/env python3
"""Static RLS coverage scanner for Supabase migrations.

The scanner finds tables that declare tenant columns but never receive
`ENABLE ROW LEVEL SECURITY` in any migration. It is intentionally static and
does not require database credentials, so it can run in CI.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TENANT_COLUMNS = ("organization_id", "org_id", "tenant_id")


def _read_sql_files() -> list[Path]:
    migrations_dir = Path(__file__).resolve().parent.parent / "supabase" / "migrations"
    if not migrations_dir.is_dir():
        print(f"ERROR: migrations directory not found: {migrations_dir}")
        sys.exit(1)
    return sorted(migrations_dir.glob("*.sql"))


def _collect_tenant_tables(sql_files: list[Path]) -> set[str]:
    create_table_re = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?([a-zA-Z_][\w]*)\s*\(",
        re.IGNORECASE,
    )
    alter_add_col_re = re.compile(
        r"ALTER\s+TABLE\s+(?:public\.)?([a-zA-Z_][\w]*)\s+ADD\s+(?:COLUMN\s+)?(?:IF\s+NOT\s+EXISTS\s+)?(organization_id|org_id|tenant_id)\b",
        re.IGNORECASE,
    )

    tables: set[str] = set()
    for path in sql_files:
        content = path.read_text(encoding="utf-8", errors="replace")
        lower = content.lower()

        for match in create_table_re.finditer(content):
            table = match.group(1).lower()
            start = match.start()
            end = lower.find(");", start)
            body = lower[start : end if end != -1 else start + 5000]
            if any(col in body for col in TENANT_COLUMNS):
                tables.add(table)

        for match in alter_add_col_re.finditer(content):
            tables.add(match.group(1).lower())

    return tables


def _collect_rls_tables(sql_files: list[Path]) -> set[str]:
    rls_re = re.compile(
        r"ALTER\s+TABLE\s+(?:public\.)?([a-zA-Z_][\w]*)\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY",
        re.IGNORECASE,
    )
    tables: set[str] = set()
    for path in sql_files:
        content = path.read_text(encoding="utf-8", errors="replace")
        tables.update(match.group(1).lower() for match in rls_re.finditer(content))
    return tables


def main() -> int:
    sql_files = _read_sql_files()
    tenant_tables = _collect_tenant_tables(sql_files)
    rls_tables = _collect_rls_tables(sql_files)

    missing = sorted(tenant_tables - rls_tables)
    covered = sorted(tenant_tables & rls_tables)

    print(f"Scanned {len(sql_files)} migration files")
    print(f"Tenant-scoped tables with RLS: {len(covered)}")
    print(f"Tenant-scoped tables missing RLS: {len(missing)}")

    if missing:
        for table in missing:
            print(f"  MISSING_RLS {table}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
