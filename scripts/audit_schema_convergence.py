"""Audit schema convergence around tenant columns and Agent Ops tables."""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
CREATE_TABLE_RE = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w.]+)\s*\((.*?)\);", re.I | re.S)


def normalize_table(raw: str) -> str:
    return raw.split(".")[-1].strip('"')


def main() -> int:
    tenant_columns: dict[str, set[str]] = defaultdict(set)
    agent_ops_tables = {
        "agent_heartbeat_runs",
        "agent_skill_health",
        "agent_reactive_triggers",
        "agent_chain_runs",
        "agent_persona_profiles",
        "agent_external_capabilities",
    }
    created_tables: set[str] = set()

    for path in sorted(MIGRATIONS.glob("*.sql")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in CREATE_TABLE_RE.finditer(text):
            table = normalize_table(match.group(1))
            created_tables.add(table)
            body = match.group(2)
            if re.search(r"\borg_id\b", body, re.I):
                tenant_columns[table].add("org_id")
            if re.search(r"\borganization_id\b", body, re.I):
                tenant_columns[table].add("organization_id")

    mixed = sorted(table for table, columns in tenant_columns.items() if len(columns) > 1)
    missing_agent_ops = sorted(agent_ops_tables - created_tables)

    if mixed:
        print("SCHEMA_CONVERGENCE_FAIL mixed tenant columns:")
        for table in mixed:
            print(f" - {table}: {sorted(tenant_columns[table])}")
    if missing_agent_ops:
        print("SCHEMA_CONVERGENCE_FAIL missing Agent Ops tables:")
        for table in missing_agent_ops:
            print(f" - {table}")
    if mixed or missing_agent_ops:
        return 1

    print("SCHEMA_CONVERGENCE_OK")
    print(f"tables_with_tenant_columns={len(tenant_columns)}")
    print(f"agent_ops_tables={len(agent_ops_tables)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
