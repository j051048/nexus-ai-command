"""Read-only private deployment readiness doctor."""

from __future__ import annotations

import os
import sys
from urllib.parse import urlparse


REQUIRED = [
    ("SUPABASE_URL", "url"),
    ("SUPABASE_SERVICE_KEY", "secret"),
    ("SUPABASE_JWT_SECRET", "secret"),
    ("REDIS_URL", "secret"),
    ("OPENAI_API_KEY", "secret"),
    ("LANGGRAPH_CHECKPOINTER", "plain"),
]

OPTIONAL = [
    "LANGGRAPH_AES_KEY",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "SENTRY_DSN",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
]


def _ok(name: str, kind: str) -> bool:
    value = os.getenv(name, "")
    if kind == "url":
        parsed = urlparse(value)
        return bool(parsed.scheme and parsed.netloc)
    return bool(value)


def main() -> int:
    production = os.getenv("ENV", "development").lower() in {"production", "prod"}
    failed = []
    print("Nexus private deployment doctor")
    print(f"ENV={os.getenv('ENV', 'development')}")
    for name, kind in REQUIRED:
        ok = _ok(name, kind)
        if production and name == "LANGGRAPH_CHECKPOINTER":
            ok = os.getenv(name, "") == "postgres"
        status = "OK" if ok else "FAIL"
        print(f"{status} required {name}")
        if not ok:
            failed.append(name)

    for name in OPTIONAL:
        print(f"{'OK' if os.getenv(name) else 'WARN'} optional {name}")

    if failed:
        print("Deployment is not ready. Missing/invalid: " + ", ".join(failed), file=sys.stderr)
        return 1
    print("Deployment readiness checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
