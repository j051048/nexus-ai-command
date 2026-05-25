"""Scan RLS tenant policy expressions for references to missing table columns.

This catches a migration failure class that static RLS coverage cannot see:
a policy can exist, but still point at an old tenant column such as ``org_id``
after the table has moved to ``organization_id``. A clean database replay then
fails while creating the policy.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"

CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?([a-zA-Z_]\w*)\s*\(",
    re.IGNORECASE,
)
ALTER_ADD_RE = re.compile(
    r"ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:public\.)?([a-zA-Z_]\w*)"
    r"\s+ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_]\w*)",
    re.IGNORECASE,
)
POLICY_RE = re.compile(
    r"CREATE\s+POLICY\s+.*?\s+ON\s+(?:public\.)?([a-zA-Z_]\w*)\b(?P<body>.*?);",
    re.IGNORECASE | re.DOTALL,
)
TENANT_COLUMN_RE = re.compile(
    r"\b([a-zA-Z_]\w*)\s*::\s*text\s*=\s*(?:public\.)?current_tenant_id_text\s*\(",
    re.IGNORECASE,
)
COLUMN_RE = re.compile(
    r"^\s*([a-zA-Z_]\w*)\s+[a-zA-Z][\w]*(?:\s*\([^)]*\))?",
    re.IGNORECASE,
)
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
class Failure:
    path: Path
    table: str
    column: str


def _find_matching_paren(sql: str, open_index: int) -> int:
    depth = 0
    quote: str | None = None
    for index in range(open_index, len(sql)):
        char = sql[index]
        if quote:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _split_top_level(body: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    quote: str | None = None
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


def _collect_table_columns(sql_files: list[Path]) -> dict[str, set[str]]:
    columns: dict[str, set[str]] = defaultdict(set)
    for path in sql_files:
        sql = path.read_text(encoding="utf-8", errors="replace")
        for match in CREATE_TABLE_RE.finditer(sql):
            table = match.group(1).lower()
            open_index = sql.find("(", match.end() - 1)
            close_index = _find_matching_paren(sql, open_index)
            if close_index == -1:
                continue
            body = sql[open_index + 1 : close_index]
            for part in _split_top_level(body):
                column_match = COLUMN_RE.match(part)
                if not column_match:
                    continue
                name = column_match.group(1)
                if name.upper() not in SKIP_COLUMN_STARTS:
                    columns[table].add(name.lower())

        for match in ALTER_ADD_RE.finditer(sql):
            table = match.group(1).lower()
            column = match.group(2).lower()
            columns[table].add(column)
    return columns


def scan() -> list[Failure]:
    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    columns_by_table = _collect_table_columns(sql_files)
    failures: list[Failure] = []
    for path in sql_files:
        sql = path.read_text(encoding="utf-8", errors="replace")
        for policy in POLICY_RE.finditer(sql):
            table = policy.group(1).lower()
            known_columns = columns_by_table.get(table, set())
            if not known_columns:
                continue
            for tenant_ref in TENANT_COLUMN_RE.finditer(policy.group("body")):
                column = tenant_ref.group(1).lower()
                if column not in known_columns:
                    failures.append(Failure(path=path, table=table, column=column))
    return failures


def main() -> int:
    failures = scan()
    print("RLS policy column scan")
    if not failures:
        print("OK")
        return 0

    print("FAIL")
    for failure in failures:
        relative = failure.path.relative_to(ROOT)
        print(f"{relative}: {failure.table}.{failure.column} is not defined")
    return 1


if __name__ == "__main__":
    sys.exit(main())
