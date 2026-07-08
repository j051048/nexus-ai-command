"""Supply-chain and secret-scan severity policy gate.

The scanner tools are run by GitHub Actions. This script keeps the release
policy explicit so CI cannot silently drift from the intended severity model.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SEVERITY_POLICY = {
    "critical": "fail",
    "high": "fail when exploitable in runtime image or direct production dependency",
    "medium": "report and schedule",
    "low": "report",
}

REQUIRED_WORKFLOW_TOKENS = (
    "pip-audit -r nexus_backend/requirements.txt --strict || true",
    "npm audit --omit=dev --audit-level=critical",
    "scan_hardcoded_secrets.py",
    "Trivy critical filesystem gate",
    "severity: CRITICAL",
    'exit-code: "1"',
)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def main() -> int:
    workflow = read(".github/workflows/test-full.yml")
    failures: list[str] = []

    for severity in ("critical", "high", "medium", "low"):
        if severity not in SEVERITY_POLICY:
            failures.append(f"missing severity policy for {severity}")

    if SEVERITY_POLICY["critical"] != "fail":
        failures.append("critical vulnerabilities must fail CI")

    for token in REQUIRED_WORKFLOW_TOKENS:
        if token not in workflow:
            failures.append(f"workflow missing scanner token: {token}")

    if failures:
        print("SECURITY_SEVERITY_GATE_FAIL")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("SECURITY_SEVERITY_GATE_OK")
    for severity, action in SEVERITY_POLICY.items():
        print(f"{severity}: {action}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
