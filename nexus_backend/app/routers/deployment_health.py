"""Private deployment readiness checks."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from fastapi import APIRouter, Depends

from app.core.dependencies import require_role
from app.core.errors import api_success

router = APIRouter(prefix="/api/system/deployment-health", tags=["System"])
require_deploy_admin = require_role(["admin", "founder", "boss"])


def _check_env(name: str, *, secret: bool = False) -> dict:
    value = os.getenv(name, "")
    return {
        "name": name,
        "ok": bool(value),
        "value": "***" if secret and value else value,
        "severity": "critical",
    }


def _check_url(name: str) -> dict:
    value = os.getenv(name, "")
    parsed = urlparse(value)
    return {
        "name": name,
        "ok": bool(parsed.scheme and parsed.netloc),
        "value": value,
        "severity": "critical",
    }


@router.get("")
@router.get("/")
async def get_deployment_health(_role: str = Depends(require_deploy_admin)):
    """Return private deployment readiness without exposing secrets."""
    checks = [
        _check_url("SUPABASE_URL"),
        _check_env("SUPABASE_SERVICE_KEY", secret=True),
        _check_env("SUPABASE_JWT_SECRET", secret=True),
        _check_env("REDIS_URL", secret=True),
        _check_env("OPENAI_API_KEY", secret=True),
        _check_env("LANGGRAPH_CHECKPOINTER"),
    ]

    optional = [
        _check_env("LANGGRAPH_AES_KEY", secret=True),
        _check_env("OTEL_EXPORTER_OTLP_ENDPOINT"),
        _check_env("SENTRY_DSN", secret=True),
        _check_env("LANGFUSE_PUBLIC_KEY", secret=True),
        _check_env("LANGFUSE_SECRET_KEY", secret=True),
    ]
    for check in optional:
        check["severity"] = "warning"

    production = os.getenv("ENV", "development").lower() in {"production", "prod"}
    if production:
        for check in checks:
            if check["name"] == "LANGGRAPH_CHECKPOINTER":
                check["ok"] = check["value"] == "postgres"
                check["message"] = "production requires LANGGRAPH_CHECKPOINTER=postgres"

    failed = [check for check in checks if not check["ok"]]
    warnings = [check for check in optional if not check["ok"]]
    return api_success(
        data={
            "ready": not failed,
            "environment": os.getenv("ENV", "development"),
            "checks": checks,
            "warnings": warnings,
            "summary": {
                "critical_failed": len(failed),
                "warning_failed": len(warnings),
                "production_mode": production,
            },
        }
    )
