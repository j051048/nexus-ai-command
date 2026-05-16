"""Collect a lightweight SOC2 Type I readiness evidence manifest.

This is intentionally offline and redacted. It gives each customer deployment a
repeatable evidence bundle that can be attached to an internal change ticket or
handoff package without exporting secrets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CONTROL_EVIDENCE = {
    "CC1_security_ownership": [
        "docs/PRODUCTION_LAUNCH_CHECKLIST.md",
        "src/config/customerLaunchModules.ts",
    ],
    "CC3_risk_readiness": [
        "scripts/production_readiness_check.mjs",
        "scripts/private_deploy_doctor.py",
        "scripts/production_health_check.mjs",
    ],
    "CC5_automated_controls": [
        "scripts/release_quality_gate.py",
        "scripts/customer_acceptance_gate.py",
        "nexus_backend/tests/unit/test_architecture_guards.py",
    ],
    "CC6_logical_access": [
        "nexus_backend/app/core/api_key_middleware.py",
        "nexus_backend/app/core/tool_rbac.py",
        "nexus_backend/app/services/permission_service.py",
        "nexus_backend/app/routers/enterprise_sso.py",
    ],
    "CC7_security_monitoring": [
        "nexus_backend/app/services/audit_logger.py",
        "nexus_backend/app/routers/compliance.py",
        "supabase/migrations/20260419_p1_audit_logs_immutable.sql",
    ],
    "CC8_change_management": [
        ".github/workflows/ci.yml",
        "supabase/migrations",
        "scripts/scan_rls_coverage.py",
    ],
    "CC9_vendor_model_risk": [
        "nexus_backend/app/services/llm_gateway",
        "nexus_backend/app/core/token_budget.py",
        "nexus_backend/app/core/model_pricing.py",
    ],
}


def hash_path(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    if path.is_file():
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    files = sorted(item for item in path.rglob("*") if item.is_file())
    for item in files:
        digest.update(str(item.relative_to(path)).encode("utf-8"))
        digest.update(hash_path(item).encode("utf-8"))
    return digest.hexdigest()


def control_status(paths: list[str]) -> dict:
    evidence = []
    for relative in paths:
        full = ROOT / relative
        evidence.append(
            {
                "path": relative,
                "exists": full.exists(),
                "kind": "directory" if full.is_dir() else "file",
                "sha256": hash_path(full),
            }
        )
    return {
        "ready": all(item["exists"] for item in evidence),
        "evidence": evidence,
    }


def collect() -> dict:
    controls = {name: control_status(paths) for name, paths in CONTROL_EVIDENCE.items()}
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "repository": ROOT.name,
        "environment": {
            "ENV": os.getenv("ENV") or False,
            "PRIVATE_DEPLOYMENT": os.getenv("PRIVATE_DEPLOYMENT") or False,
            "LANGGRAPH_CHECKPOINTER": os.getenv("LANGGRAPH_CHECKPOINTER") or False,
        },
        "controls": controls,
        "summary": {
            "controls_total": len(controls),
            "controls_ready": sum(1 for item in controls.values() if item["ready"]),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect SOC2 readiness evidence")
    parser.add_argument("--output", default="dist/soc2-evidence.json")
    args = parser.parse_args()
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = collect()
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = manifest["summary"]
    print(f"SOC2 evidence written to {output}")
    print(f"Controls ready: {summary['controls_ready']}/{summary['controls_total']}")
    return 0 if summary["controls_ready"] == summary["controls_total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
