#!/usr/bin/env python3
"""Focused mypy gate for the cost, quota and rate-limit path.

These five modules decide money and admission control, so they get a real type
check while the rest of the backend stays on the lighter ruff/black gates.

The target list lives here rather than inside one workflow on purpose: mypy ran
only in the scheduled Full Test Suite, so a type error could sit red for a day
after the push that introduced it. Both workflows now call this script, which
keeps the two definitions from drifting apart.

``--follow-imports=skip`` keeps the check fast, but it also means a helper
imported from a non-listed module looks like ``Any``. Every module this path
depends on must therefore be listed in ``TARGETS``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "nexus_backend"

TARGETS = (
    "app/core/config.py",
    "app/core/rate_limiter.py",
    "app/core/token_budget.py",
    # token_budget/rate_limiter normalize REDIS_URL through this module; leaving
    # it out makes its return type `Any` and produced a `no-any-return` error.
    "app/core/redis_url.py",
    "app/services/agent_eval_baseline_service.py",
    "app/services/agent_ops_runtime_service.py",
)

FLAGS = (
    "--ignore-missing-imports",
    "--no-strict-optional",
    "--follow-imports=skip",
    "--show-error-codes",
)


def main() -> int:
    missing = [target for target in TARGETS if not (BACKEND / target).exists()]
    if missing:
        print("BACKEND_TYPES_FAIL")
        for target in missing:
            print(f" - target moved or deleted: {target}")
        return 1

    probe = subprocess.run(
        [sys.executable, "-c", "import mypy"], check=False, capture_output=True
    )
    if probe.returncode != 0:
        print("BACKEND_TYPES_FAIL")
        print(f" - mypy is not installed for {sys.executable}")
        print("   fix: nexus_backend/.venv/Scripts/python scripts/check_backend_types.py")
        print("        (or pip install -r nexus_backend/requirements-dev.txt)")
        return 1

    result = subprocess.run(
        [sys.executable, "-m", "mypy", *TARGETS, *FLAGS],
        cwd=BACKEND,
        check=False,
    )
    if result.returncode != 0:
        print("BACKEND_TYPES_FAIL")
        return 1
    print(f"BACKEND_TYPES_OK files={len(TARGETS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
