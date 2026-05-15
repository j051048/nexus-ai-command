"""Read-only private deployment readiness doctor."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    ("SUPABASE_URL", "url"),
    ("SUPABASE_SERVICE_KEY", "secret"),
    ("SUPABASE_JWT_SECRET", "secret"),
    ("REDIS_URL", "secret"),
    ("OPENAI_API_KEY", "secret"),
    ("LANGGRAPH_CHECKPOINTER", "plain"),
    ("ENCRYPTION_KEY", "secret"),
    ("HEALTH_CHECK_TOKEN", "secret"),
]

OPTIONAL = [
    "LANGGRAPH_AES_KEY",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "SENTRY_DSN",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
]

REQUIRED_FILES = [
    "Dockerfile",
    "docker-compose.yml",
    ".env.production.example",
    "scripts/backup_supabase.sh",
    "scripts/backup_supabase.ps1",
    "scripts/release_quality_gate.py",
    "scripts/check_bundle_budget.mjs",
    "scripts/collect_release_evidence.py",
]


def _load_env_file(path: str | None) -> None:
    if not path:
        return
    full_path = Path(path)
    if not full_path.is_absolute():
        full_path = ROOT / full_path
    if not full_path.exists():
        print(f"WARN env file not found: {full_path}")
        return
    for line in full_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _ok(name: str, kind: str) -> bool:
    value = os.getenv(name, "")
    if kind == "url":
        parsed = urlparse(value)
        return bool(parsed.scheme and parsed.netloc)
    return bool(value)


def _file_ok(path: str) -> bool:
    return (ROOT / path).exists()


def _cors_locked_down() -> bool:
    value = os.getenv("CORS_ORIGINS", "")
    return bool(value and "*" not in value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only private deployment readiness doctor")
    parser.add_argument("--env", default=None, help="Optional env file to load before checks")
    args = parser.parse_args()
    _load_env_file(args.env)

    production = os.getenv("ENV", "development").lower() in {"production", "prod"}
    private_deployment = os.getenv("PRIVATE_DEPLOYMENT", "").lower() in {"1", "true", "yes"}
    failed = []
    warnings = []
    print("Nexus private deployment doctor")
    print(f"ENV={os.getenv('ENV', 'development')}")
    print(f"PRIVATE_DEPLOYMENT={private_deployment}")
    for name, kind in REQUIRED:
        ok = _ok(name, kind)
        if production and name == "LANGGRAPH_CHECKPOINTER":
            ok = os.getenv(name, "") == "postgres"
        if name in {"ENCRYPTION_KEY", "HEALTH_CHECK_TOKEN"}:
            ok = ok and len(os.getenv(name, "")) >= 24
        status = "OK" if ok else "FAIL"
        print(f"{status} required {name}")
        if not ok:
            failed.append(name)

    for name in OPTIONAL:
        print(f"{'OK' if os.getenv(name) else 'WARN'} optional {name}")
        if not os.getenv(name):
            warnings.append(name)

    if production:
        cors_ok = _cors_locked_down()
        debug_ok = os.getenv("DEBUG", "false").lower() != "true"
        print(f"{'OK' if cors_ok else 'FAIL'} production CORS_ORIGINS locked down")
        print(f"{'OK' if debug_ok else 'FAIL'} production DEBUG disabled")
        if not cors_ok:
            failed.append("CORS_ORIGINS")
        if not debug_ok:
            failed.append("DEBUG=false")

    if private_deployment:
        for path in REQUIRED_FILES:
            ok = _file_ok(path)
            print(f"{'OK' if ok else 'FAIL'} private file {path}")
            if not ok:
                failed.append(path)

    if failed:
        print("Deployment is not ready. Missing/invalid: " + ", ".join(failed), file=sys.stderr)
        return 1
    print(f"Deployment readiness checks passed with {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
