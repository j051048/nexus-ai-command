"""Generate a customer handoff report for local/private deployments."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "dist" / "customer-handoff.md"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def module_list() -> list[str]:
    env_text = read(".env.production.example")
    for line in env_text.splitlines():
        if line.startswith("VITE_ENABLED_MODULES="):
            return [item.strip() for item in line.split("=", 1)[1].split(",") if item.strip()]
    return []


def evidence_summary() -> str:
    evidence_path = ROOT / "dist" / "release-evidence.json"
    if not evidence_path.exists():
        return "Release evidence manifest has not been generated yet."
    data = json.loads(evidence_path.read_text(encoding="utf-8"))
    present = sum(1 for item in data.get("files", []) if item.get("exists"))
    total = len(data.get("files", []))
    return f"Release evidence manifest present: {present}/{total} files captured."


def build_report() -> str:
    modules = module_list()
    lines = [
        "# Nexus AI Command Customer Handoff",
        "",
        f"Generated at: {datetime.now(UTC).isoformat()}",
        "",
        "## Launch Profile",
        "",
        "- Profile: `small_company`",
        f"- Enabled modules: {', '.join(modules)}",
        "",
        "## Required Acceptance Commands",
        "",
        "```bash",
        "python scripts/customer_acceptance_gate.py",
        "python scripts/release_quality_gate.py",
        "node scripts/production_readiness_check.mjs --env .env.production",
        "npm run build",
        "npm run check:bundle",
        "npm run test:e2e -- e2e/top10-critical-flows.spec.ts --project=chromium",
        "npm run test:e2e -- e2e/customer-business-acceptance.spec.ts --project=chromium",
        "```",
        "",
        "## Evidence",
        "",
        f"- {evidence_summary()}",
        "- RLS scanner must report zero missing RLS and zero missing tenant policies.",
        "- Backup and restore drill result must be attached by the deployment engineer.",
        "",
        "## Customer Operating Scope",
        "",
        "- AI suggestions are allowed for all enabled modules.",
        "- Irreversible write actions require human confirmation.",
        "- Tool usage, data mutations, API key calls, and compliance exports must remain auditable.",
        "- Optional integrations are not accepted until real customer credentials are configured.",
        "",
        "## Handoff Notes",
        "",
        "- Keep `VITE_LAUNCH_PROFILE=small_company` for first production rollout.",
        "- Enable `extended` only after the customer signs off the default module set.",
        "- Use `docs/PRIVATE_DEPLOYMENT_PGBOUNCER.md` when deploying with local Postgres.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate customer handoff markdown")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output markdown path")
    args = parser.parse_args()
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_report(), encoding="utf-8")
    print(f"Customer handoff written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
