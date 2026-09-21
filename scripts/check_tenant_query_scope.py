#!/usr/bin/env python3
"""Fail when unscoped service-role table access grows.

The backend talks to PostgREST with ``SUPABASE_SERVICE_KEY``, which bypasses
RLS by design. Tenant isolation therefore depends on every query carrying an
organization filter. RLS policies still exist, but they are not what protects
these code paths.

This guard freezes the current amount of unscoped access per file (managed
debt) and forbids new files from starting with any. Move a call site into
``get_org_filtered_client(...)`` (or add an explicit ``organization_id``
filter / ``p_org_id`` RPC parameter) and rerun with ``--update`` to lower the
baseline.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "nexus_backend" / "app"
BASELINE_PATH = ROOT / "docs" / "quality" / "tenant-query-scope-baseline.json"

# Tables that intentionally have no organization column: platform-level
# catalogs, tenant registry itself, and per-user identity rows resolved before
# the organization context exists.
GLOBAL_TABLES = {
    "organizations",
    "organization_members",
    "organization_invites",
    "profiles",
    "user_profiles",
    "users",
    "auth_users",
    "llm_models",
    "llm_pricing",
    "system_settings",
    "platform_settings",
    "feature_flags",
    "schema_migrations",
    "agent_eval_baselines",
    "public_plans",
    "industry_benchmarks",
    "instrument_catalog",
    # Platform operations ledger: records what a retention sweep deleted. It has
    # no organization column by design (see 20260921_002 migration) so org
    # admins cannot infer another tenant's volume.
    "data_retention_runs",
}

ORG_TOKENS = ("organization_id", "org_id", "tenant_id", "p_org_id", "org_filtered")
STATEMENT_NODES = (ast.Expr, ast.Assign, ast.AnnAssign, ast.Return, ast.AugAssign)


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    mapping: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            mapping[child] = node
    return mapping


def _enclosing_statement(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST:
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, STATEMENT_NODES):
            return current
    return node


def _table_name(call: ast.Call) -> str | None:
    if not call.args:
        return None
    arg = call.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    return None


def analyze_source(source: str) -> tuple[int, list[str]]:
    """Return (unscoped_call_count, samples) for a single module source."""
    try:
        tree = ast.parse(source)
    except SyntaxError:  # pragma: no cover - invalid python fails other gates
        return 0, []

    parents = _parents(tree)
    unscoped = 0
    samples: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr not in {"table", "from_"}:
            continue
        table = _table_name(node)
        if table is not None and table in GLOBAL_TABLES:
            continue
        statement = _enclosing_statement(node, parents)
        segment = ast.get_source_segment(source, statement) or ""
        if any(token in segment for token in ORG_TOKENS):
            continue
        unscoped += 1
        if len(samples) < 3:
            samples.append(f"L{node.lineno}: {table or '<dynamic>'}")
    return unscoped, samples


def analyze_file(path: Path) -> tuple[int, list[str]]:
    return analyze_source(path.read_text(encoding="utf-8", errors="replace"))


def scan() -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in sorted(APP_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        count, _ = analyze_file(path)
        if count:
            counts[path.relative_to(ROOT).as_posix()] = count
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true", help="rewrite the baseline")
    parser.add_argument("--report", action="store_true", help="print worst offenders")
    args = parser.parse_args()

    counts = scan()
    total = sum(counts.values())

    if args.report:
        for name, value in sorted(counts.items(), key=lambda item: -item[1])[:25]:
            print(f"{value:5d}  {name}")
        print(f"total unscoped call sites: {total} across {len(counts)} files")
        return 0

    if args.update:
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_by": "scripts/check_tenant_query_scope.py",
            "note": "Managed debt: unscoped service-role table access per file. May only decrease.",
            "total": total,
            "files": dict(sorted(counts.items())),
        }
        BASELINE_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"TENANT_QUERY_SCOPE_BASELINE_WRITTEN total={total} files={len(counts)}")
        return 0

    if not BASELINE_PATH.exists():
        print("TENANT_QUERY_SCOPE_FAIL baseline missing; run with --update")
        return 1

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    allowed: dict[str, int] = baseline.get("files", {})

    failures: list[str] = []
    for name, value in sorted(counts.items()):
        limit = allowed.get(name)
        if limit is None:
            failures.append(f"{name}: {value} unscoped table calls in a file with no baseline")
        elif value > limit:
            failures.append(f"{name}: {value} unscoped calls exceeds baseline {limit}")

    baseline_total = int(baseline.get("total", 0))
    if total > baseline_total:
        failures.append(f"total {total} exceeds baseline {baseline_total}")

    if failures:
        print("TENANT_QUERY_SCOPE_FAIL")
        for failure in failures:
            print(f" - {failure}")
        print("Use get_org_filtered_client(...) or add an organization_id filter.")
        return 1

    print(
        f"TENANT_QUERY_SCOPE_OK unscoped={total} baseline={baseline_total} "
        f"files={len(counts)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
