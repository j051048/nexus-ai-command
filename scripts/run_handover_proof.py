#!/usr/bin/env python3
"""Run the deterministic proof pack used during engineering handover."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(label: str, command: list[str], cwd: Path = ROOT) -> None:
    print(f"\n== {label} ==")
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Also run compile, tests and build")
    args = parser.parse_args()
    npm = "npm.cmd" if os.name == "nt" else "npm"
    npx = "npx.cmd" if os.name == "nt" else "npx"

    run("handover readiness", [sys.executable, "scripts/check_handover_readiness.py"])
    run("exception governance", [sys.executable, "scripts/check_exception_governance.py"])
    run("migration governance", [sys.executable, "scripts/check_migration_governance.py"])
    run("source size", ["node", "scripts/check_source_size.mjs"])
    run("production proof contracts", [sys.executable, "scripts/production_proof_gate.py"])

    if args.full:
        run("TypeScript", [npx, "tsc", "--noEmit"])
        run("frontend tests", [npm, "test", "--", "--run"])
        run("frontend build", [npm, "run", "build"])
        run(
            "backend domain contracts",
            [sys.executable, "-m", "pytest", "tests/unit/test_domain_registry.py", "-q"],
            ROOT / "nexus_backend",
        )
    print("\nHANDOVER_PROOF_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
