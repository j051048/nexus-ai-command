#!/usr/bin/env python3
"""Prevent broad exception handling debt from growing unnoticed."""

from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "nexus_backend" / "app"
BASELINE = ROOT / "docs" / "handbook" / "generated" / "exception_debt.json"


def is_broad(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    if isinstance(handler.type, ast.Name):
        return handler.type.id in {"Exception", "BaseException"}
    if isinstance(handler.type, ast.Tuple):
        return any(
            isinstance(item, ast.Name) and item.id in {"Exception", "BaseException"}
            for item in handler.type.elts
        )
    return False


def scan() -> dict[str, object]:
    by_area: Counter[str] = Counter()
    by_file: Counter[str] = Counter()
    for path in sorted(APP_ROOT.rglob("*.py")):
        relative = path.relative_to(APP_ROOT)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as error:
            raise RuntimeError(f"Cannot parse {relative}: {error}") from error
        count = sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, ast.ExceptHandler) and is_broad(node)
        )
        if count:
            by_area[relative.parts[0]] += count
            by_file[relative.as_posix()] += count
    return {
        "total": sum(by_area.values()),
        "by_area": dict(sorted(by_area.items())),
        "top_files": dict(by_file.most_common(30)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args()
    current = scan()
    if args.write_baseline:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Wrote broad-exception baseline: {current['total']}")
        return 0
    if not BASELINE.exists():
        print("EXCEPTION_GOVERNANCE_FAIL missing baseline")
        return 1
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    failures: list[str] = []
    if int(current["total"]) > int(baseline["total"]):
        failures.append(f"total {current['total']} > {baseline['total']}")
    current_areas = current["by_area"]
    baseline_areas = baseline["by_area"]
    assert isinstance(current_areas, dict) and isinstance(baseline_areas, dict)
    for area, count in current_areas.items():
        if int(count) > int(baseline_areas.get(area, 0)):
            failures.append(f"{area} {count} > {baseline_areas.get(area, 0)}")
    if failures:
        print("EXCEPTION_GOVERNANCE_FAIL " + "; ".join(failures))
        return 1
    print(f"EXCEPTION_GOVERNANCE_OK broad catches={current['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
