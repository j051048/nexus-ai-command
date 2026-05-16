"""Collect a redacted local release evidence manifest.

The script is intentionally read-only. It records file presence, SHA-256 hashes,
and selected environment posture without storing secrets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EVIDENCE_FILES = [
    "Dockerfile",
    "docker-compose.yml",
    ".env.production.example",
    ".github/workflows/ci.yml",
    ".github/workflows/nightly-agent-quality.yml",
    "scripts/production_readiness_check.mjs",
    "scripts/production_health_check.mjs",
    "scripts/release_quality_gate.py",
    "scripts/check_bundle_budget.mjs",
    "scripts/private_deploy_doctor.py",
    "scripts/scan_rls_coverage.py",
    "scripts/customer_acceptance_gate.py",
    "scripts/agent_replay_nightly.py",
    "scripts/collect_soc2_evidence.py",
    "scripts/generate_customer_handoff.py",
    "e2e/customer-business-acceptance.spec.ts",
    "src/components/product/LaunchChecklistPanel.tsx",
    "src/pages/CustomerSuccessPage.tsx",
    "src/pages/DeploymentReadinessPage.tsx",
    "src/pages/PermissionMatrixPage.tsx",
    "nexus_backend/tests/k6/small_company.js",
    "docs/PRODUCTION_LAUNCH_CHECKLIST.md",
    "docs/RUNBOOK_SMALL_COMPANY.md",
    "docs/CUSTOMER_ACCEPTANCE_CRITERIA.md",
    "docs/PRIVATE_DEPLOYMENT_PGBOUNCER.md",
    "docs/SOC2_CONTROLS.md",
    "docs/TOOL_DEVELOPMENT_GUIDE.md",
    "supabase/migrations/20260514_p0_document_embeddings_vector_index.sql",
    "supabase/migrations/20260514_p0_tenant_rls_policy_backfill.sql",
    "supabase/migrations/20260514_p2_cost_report_rpc.sql",
]

ENV_KEYS = [
    "ENV",
    "DEBUG",
    "PRIVATE_DEPLOYMENT",
    "LANGGRAPH_CHECKPOINTER",
    "CORS_ORIGINS",
    "MAX_CONCURRENT_LLM_PER_TENANT",
    "TOKEN_BUDGET_MAX_COST_PER_MONTH_PER_TENANT",
]


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def redacted_env() -> dict[str, str | bool]:
    values: dict[str, str | bool] = {}
    for key in ENV_KEYS:
        value = os.getenv(key)
        values[key] = value if value not in (None, "") else False
    for key in os.environ:
        if any(marker in key for marker in ("KEY", "SECRET", "TOKEN", "PASSWORD")):
            values[key] = "<redacted>" if os.getenv(key) else False
    return values


def collect() -> dict[str, object]:
    files = []
    for relative in EVIDENCE_FILES:
        full_path = ROOT / relative
        files.append(
            {
                "path": relative,
                "exists": full_path.exists(),
                "sha256": sha256_file(full_path),
            }
        )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "repository": ROOT.name,
        "evidence_version": "p3-p6",
        "files": files,
        "environment": redacted_env(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect release evidence manifest")
    parser.add_argument(
        "--output",
        default="dist/release-evidence.json",
        help="Output JSON path, relative to repository root by default.",
    )
    args = parser.parse_args()
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = collect()
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    missing = [item["path"] for item in manifest["files"] if not item["exists"]]
    print(f"Release evidence written to {output}")
    print(f"Evidence files: {len(manifest['files']) - len(missing)} present, {len(missing)} missing")
    if missing:
        for path in missing:
            print(f"Missing evidence file: {path}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
