#!/usr/bin/env python3
"""Static handover gate for documentation, ownership and generated facts."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    ".github/CODEOWNERS",
    "docs/architecture.md",
    "docs/adr/005-handover-governance-and-gradual-boundaries.md",
    "docs/handbook/00-start-here.md",
    "docs/handbook/01-system-map.md",
    "docs/handbook/02-local-development.md",
    "docs/handbook/03-runtime-and-deployment.md",
    "docs/handbook/04-database-and-migrations.md",
    "docs/handbook/05-agent-lifecycle.md",
    "docs/handbook/06-security-and-tenancy.md",
    "docs/handbook/07-testing-and-release.md",
    "docs/handbook/08-troubleshooting.md",
    "docs/handbook/09-known-debt.md",
    "docs/handbook/10-sales-and-implementation.md",
    "docs/handbook/11-slo-and-ownership.md",
)


def broken_readme_links() -> list[str]:
    content = (ROOT / "README.md").read_text(encoding="utf-8")
    links = re.findall(r"\[[^]]+\]\(([^)]+)\)", content)
    broken: list[str] = []
    for target in links:
        target = target.strip().split("#", 1)[0]
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        if not (ROOT / target).exists():
            broken.append(target)
    return broken


def main() -> int:
    failures = [f"missing {path}" for path in REQUIRED if not (ROOT / path).exists()]
    failures.extend(f"README broken link {path}" for path in broken_readme_links())
    inventory = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_handover_inventory.py"), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if inventory.returncode:
        failures.append(inventory.stdout.strip() or inventory.stderr.strip())
    if failures:
        print("HANDOVER_READINESS_FAIL")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("HANDOVER_READINESS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
