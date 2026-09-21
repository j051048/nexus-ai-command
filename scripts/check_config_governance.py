#!/usr/bin/env python3
"""Freeze direct environment access outside the configuration layer.

`app/core/config.py` owns runtime configuration. Scattered `os.getenv` calls
outside that layer cannot be validated at startup, so a typo silently becomes
`None` in production. This gate records the current per-file count and fails on
growth; move new settings into `app/core/config.py` (pydantic settings) instead.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "nexus_backend" / "app"
CONFIG_ROOT = APP_ROOT / "core"
BASELINE_PATH = ROOT / "docs" / "quality" / "config-access-baseline.json"

PATTERN = re.compile(r"os\.(getenv|environ)")


def scan() -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in sorted(APP_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        if CONFIG_ROOT in path.parents:
            continue
        found = len(PATTERN.findall(path.read_text(encoding="utf-8", errors="replace")))
        if found:
            counts[path.relative_to(ROOT).as_posix()] = found
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    counts = scan()
    total = sum(counts.values())

    if args.report:
        for name, value in sorted(counts.items(), key=lambda item: -item[1])[:25]:
            print(f"{value:5d}  {name}")
        print(f"total direct env reads outside app/core: {total} across {len(counts)} files")
        return 0

    if args.update:
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(
            json.dumps(
                {
                    "generated_by": "scripts/check_config_governance.py",
                    "note": "Direct os.getenv/os.environ reads outside app/core. May only decrease.",
                    "total": total,
                    "files": dict(sorted(counts.items())),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"CONFIG_GOVERNANCE_BASELINE_WRITTEN total={total} files={len(counts)}")
        return 0

    if not BASELINE_PATH.exists():
        print("CONFIG_GOVERNANCE_FAIL baseline missing; run with --update")
        return 1

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    allowed: dict[str, int] = baseline.get("files", {})

    failures: list[str] = []
    for name, value in sorted(counts.items()):
        limit = allowed.get(name)
        if limit is None:
            failures.append(
                f"{name}: {value} direct env reads in a file with no baseline; "
                "declare the setting in app/core/config.py"
            )
        elif value > limit:
            failures.append(f"{name}: {value} direct env reads exceeds baseline {limit}")

    baseline_total = int(baseline.get("total", 0))
    if total > baseline_total:
        failures.append(f"total {total} exceeds baseline {baseline_total}")

    if failures:
        print("CONFIG_GOVERNANCE_FAIL")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print(
        f"CONFIG_GOVERNANCE_OK direct_env_reads={total} baseline={baseline_total} "
        f"files={len(counts)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
