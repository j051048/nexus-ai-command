"""Verify deployed schema objects before repairing migration-history gaps.

This tool is intentionally conservative. It never executes migration SQL and it
never records a migration whose required tables or columns are absent. Run it
without ``--apply`` first; production reconciliation requires the service key.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
MIGRATION_NAME = re.compile(r"^\d{8}.*\.sql$")
CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?[\"']?([a-zA-Z_][\w]*)",
    re.IGNORECASE,
)
ALTER_ADD_COLUMN = re.compile(
    r"ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:public\.)?[\"']?([a-zA-Z_][\w]*)[\"']?"
    r"(?P<body>.*?)(?=;)",
    re.IGNORECASE | re.DOTALL,
)
ADD_COLUMN = re.compile(
    r"ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"']?([a-zA-Z_][\w]*)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MigrationContract:
    name: str
    checksum: str
    tables: tuple[str, ...] = ()
    columns: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def verifiable(self) -> bool:
        return bool(self.tables or self.columns)


def migration_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_contract(path: Path) -> MigrationContract:
    sql = path.read_text(encoding="utf-8")
    tables = sorted(set(CREATE_TABLE.findall(sql)) - {"migration_history"})
    columns: dict[str, set[str]] = {}
    for match in ALTER_ADD_COLUMN.finditer(sql):
        table = match.group(1)
        additions = set(ADD_COLUMN.findall(match.group("body")))
        if additions:
            columns.setdefault(table, set()).update(additions)
    return MigrationContract(
        name=path.name,
        checksum=migration_checksum(path),
        tables=tuple(tables),
        columns={key: tuple(sorted(value)) for key, value in sorted(columns.items())},
    )


def migration_contracts(name: str | None = None) -> list[MigrationContract]:
    paths = sorted(
        path
        for path in MIGRATIONS.iterdir()
        if path.is_file() and MIGRATION_NAME.match(path.name)
    )
    if name:
        normalized = name if name.endswith(".sql") else f"{name}.sql"
        paths = [path for path in paths if path.name == normalized]
        if not paths:
            raise ValueError(f"migration not found: {normalized}")
    return [extract_contract(path) for path in paths]


def _api_request(
    *, url: str, service_key: str, method: str, path: str, payload: Any | None = None
) -> Any:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{url.rstrip('/')}{path}",
        data=body,
        method=method,
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read().decode("utf-8")
            return json.loads(content) if content else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase API {exc.code}: {detail[:1000]}") from exc


def reconcile(
    contract: MigrationContract, *, url: str, service_key: str, apply: bool
) -> dict[str, Any]:
    result = _api_request(
        url=url,
        service_key=service_key,
        method="POST",
        path="/rest/v1/rpc/reconcile_migration_history",
        payload={
            "p_migration_name": contract.name,
            "p_checksum": contract.checksum,
            "p_required_tables": list(contract.tables),
            "p_required_columns": {
                table: list(columns) for table, columns in contract.columns.items()
            },
            "p_apply": apply,
        },
    )
    return dict(result or {})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="record verified gaps")
    parser.add_argument("--name", help="reconcile one migration")
    parser.add_argument("--fail-on-unverified", action="store_true")
    args = parser.parse_args()

    url = os.getenv("SUPABASE_URL", "").strip()
    service_key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    if not url or not service_key:
        print("SUPABASE_URL and SUPABASE_SERVICE_KEY are required", file=sys.stderr)
        return 2

    verified = recorded = skipped = failed = 0
    for contract in migration_contracts(args.name):
        if not contract.verifiable:
            skipped += 1
            print(f"SKIP {contract.name}: no conservative table/column contract")
            continue
        result = reconcile(
            contract, url=url, service_key=service_key, apply=bool(args.apply)
        )
        if result.get("verified"):
            verified += 1
            recorded += int(bool(result.get("recorded")))
            mode = "RECORDED" if result.get("recorded") else "VERIFIED"
            print(f"{mode} {contract.name}")
        else:
            failed += 1
            print(
                f"MISSING {contract.name}: tables={result.get('missing_tables', [])} "
                f"columns={result.get('missing_columns', [])}"
            )
    print(
        f"Migration reconciliation: verified={verified} recorded={recorded} "
        f"skipped={skipped} unverified={failed} apply={bool(args.apply)}"
    )
    return 1 if args.fail_on_unverified and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
