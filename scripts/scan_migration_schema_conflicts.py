"""Scan SQL migrations for duplicate CREATE TABLE schema conflicts.

`CREATE TABLE IF NOT EXISTS` is safe only when every repeated definition is
schema-compatible. Otherwise Postgres silently keeps the old shape and later
code may query columns that do not exist. This scanner catches that class.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"
ALLOW_RECONCILE_CREATE = "schema-conflict-scan: allow-reconcile-create"
CREATE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?([a-zA-Z_][\w]*)\s*\(",
    re.IGNORECASE,
)
COLUMN_RE = re.compile(r"^\s*([a-zA-Z_][\w]*)\s+([a-zA-Z][\w]*(?:\s*\([^)]*\))?)", re.IGNORECASE)
SKIP_COLUMN_STARTS = {
    "CONSTRAINT",
    "PRIMARY",
    "UNIQUE",
    "FOREIGN",
    "CHECK",
    "EXCLUDE",
    "LIKE",
}


@dataclass(frozen=True)
class TableDefinition:
    path: Path
    table: str
    columns: dict[str, str]


def _find_matching_paren(sql: str, start_index: int) -> int:
    depth = 0
    for index in range(start_index, len(sql)):
        char = sql[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _split_top_level_columns(body: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    quote: str | None = None
    current: list[str] = []
    for char in body:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            current.append(char)
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def extract_definitions(path: Path) -> list[TableDefinition]:
    sql = path.read_text(encoding="utf-8", errors="replace")
    if ALLOW_RECONCILE_CREATE in sql:
        return []
    definitions: list[TableDefinition] = []
    for match in CREATE_RE.finditer(sql):
        table = match.group(1)
        open_paren = sql.find("(", match.end() - 1)
        close_paren = _find_matching_paren(sql, open_paren)
        if close_paren == -1:
            continue
        body = sql[open_paren + 1 : close_paren]
        columns: dict[str, str] = {}
        for part in _split_top_level_columns(body):
            column_match = COLUMN_RE.match(part)
            if not column_match:
                continue
            name = column_match.group(1)
            if name.upper() in SKIP_COLUMN_STARTS:
                continue
            columns[name.lower()] = re.sub(r"\s+", " ", column_match.group(2).lower())
        definitions.append(TableDefinition(path=path, table=table.lower(), columns=columns))
    return definitions


def main() -> int:
    by_table: dict[str, list[TableDefinition]] = {}
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        for definition in extract_definitions(path):
            by_table.setdefault(definition.table, []).append(definition)

    failures: list[str] = []
    print("Migration schema conflict scan")
    for table, definitions in sorted(by_table.items()):
        if len(definitions) < 2:
            continue
        baseline = definitions[0]
        for candidate in definitions[1:]:
            if baseline.columns != candidate.columns:
                failures.append(
                    f"{table}: {baseline.path.name} differs from {candidate.path.name}"
                )
                base_only = sorted(set(baseline.columns) - set(candidate.columns))
                candidate_only = sorted(set(candidate.columns) - set(baseline.columns))
                if base_only:
                    failures.append(f"  only in baseline: {', '.join(base_only)}")
                if candidate_only:
                    failures.append(f"  only in candidate: {', '.join(candidate_only)}")

    if failures:
        print("FAIL")
        for item in failures:
            print(item)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
