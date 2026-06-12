"""Validate the backend OpenAPI contract used by frontend and E2E tests.

This is intentionally deterministic and offline. It imports the FastAPI app,
generates the OpenAPI schema, and checks invariants that catch accidental API
surface regressions before the browser or deployment tests discover them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "nexus_backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


REQUIRED_PATHS = {
    "/health/live",
    "/health/ready",
    "/health",
    "/api/chat",
    "/api/dashboard/ai-weekly-report",
    "/api/ai-operating-system/aeon-inspired-ops",
}


def main() -> int:
    from app.main import app

    schema = app.openapi()
    paths = schema.get("paths", {})
    missing = sorted(path for path in REQUIRED_PATHS if path not in paths)
    if missing:
        print("OPENAPI_CONTRACT_FAIL missing paths:")
        for path in missing:
            print(f" - {path}")
        return 1

    operation_ids: dict[str, str] = {}
    duplicates: list[str] = []
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, operation in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            operation_id = operation.get("operationId")
            if not operation_id:
                print(f"OPENAPI_CONTRACT_FAIL missing operationId: {method.upper()} {path}")
                return 1
            previous = operation_ids.setdefault(operation_id, f"{method.upper()} {path}")
            if previous != f"{method.upper()} {path}":
                duplicates.append(f"{operation_id}: {previous} / {method.upper()} {path}")

    if duplicates:
        print("OPENAPI_CONTRACT_FAIL duplicate operationIds:")
        for item in duplicates:
            print(f" - {item}")
        return 1

    output_path = ROOT / "openapi-contract.generated.json"
    output_path.write_text(
        json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    print(f"OPENAPI_CONTRACT_OK paths={len(paths)} output={output_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
