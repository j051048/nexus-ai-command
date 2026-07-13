"""Nightly Agent replay promotion and health runner.

When AGENT_REPLAY_BASE_URL and AGENT_REPLAY_TOKEN are configured, this script
calls the production/staging replay API to promote recent failures into eval
cases. Without credentials it performs static readiness checks so scheduled CI
still guards against accidental removal of the replay harness.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

STATIC_REPLAY_FILES = [
    "nexus_backend/app/routers/agent_replay.py",
    "nexus_backend/app/services/agent_replay_service.py",
    "nexus_backend/app/services/eval_case_promotion_service.py",
    "src/pages/AgentRunsPage.tsx",
]


def static_check() -> tuple[int, dict]:
    missing = [path for path in STATIC_REPLAY_FILES if not (ROOT / path).exists()]
    if missing:
        print("Agent replay static check failed:")
        for path in missing:
            print(f" - missing {path}")
        return 1, {"status": "STATIC_FAILED", "missing": missing}
    router = (ROOT / "nexus_backend/app/routers/agent_replay.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    required_tokens = [
        "/eval-cases/promote-failures",
        "/eval-cases",
        "compare_sessions",
        "get_checkpoint_history",
        '"/run-case"',
    ]
    missing_tokens = [token for token in required_tokens if token not in router]
    if missing_tokens:
        print("Agent replay static check failed:")
        for token in missing_tokens:
            print(f" - missing token {token}")
        return 1, {"status": "STATIC_FAILED", "missing_tokens": missing_tokens}
    result = {
        "status": "STATIC_READY",
        "message": "Replay harness contracts are present; no runtime replay was executed.",
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0, result


def post_json(url: str, token: str, payload: dict | None = None) -> dict:
    request = urllib.request.Request(
        url,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload or {}).encode("utf-8"),
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8")
        return json.loads(payload) if payload else {}


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="Fail when staging replay credentials are unavailable.",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    base_url = os.getenv("AGENT_REPLAY_BASE_URL", "").rstrip("/")
    token = os.getenv("AGENT_REPLAY_TOKEN", "")
    if not base_url or not token:
        static_code, static_result = static_check()
        if static_code:
            return static_code
        result = {
            **static_result,
            "status": "REPLAY_SKIPPED",
            "reason": "AGENT_REPLAY_BASE_URL or AGENT_REPLAY_TOKEN is missing",
        }
        print(json.dumps(result, ensure_ascii=False))
        return 1 if args.require_live else 0

    replay_endpoint = f"{base_url}/api/agent/replay/run-case"
    promotion_endpoint = (
        f"{base_url}/api/agent/replay/eval-cases/promote-failures?limit=50"
    )
    try:
        replay_response = post_json(
            replay_endpoint,
            token,
            {
                "id": "nightly-health",
                "message": "Reply with a concise health acknowledgement. Do not call tools.",
                "agent_code": "director_agent",
                "expectations": {
                    "forbidden_tools": [
                        "send_external_email",
                        "approve_payment",
                        "delete_customer",
                    ],
                    "max_errors": 0,
                    "max_duration_ms": 60000,
                },
            },
        )
        replay_data = replay_response.get("data") or {}
        if replay_data.get("passed") is not True:
            print(
                json.dumps(
                    {"status": "REPLAY_FAILED", "result": replay_response},
                    ensure_ascii=False,
                )
            )
            return 1
        promotion_response = post_json(promotion_endpoint, token)
    except urllib.error.HTTPError as exc:
        print(f"Agent replay promotion failed: HTTP {exc.code}", file=sys.stderr)
        print(exc.read().decode("utf-8", errors="replace")[:1000], file=sys.stderr)
        print(json.dumps({"status": "REPLAY_FAILED", "http_status": exc.code}))
        return 1
    except Exception as exc:
        print(f"Agent replay promotion failed: {exc}", file=sys.stderr)
        print(json.dumps({"status": "REPLAY_FAILED", "error": str(exc)}))
        return 1

    result = {
        "status": "REPLAY_PASSED",
        "replay": replay_response,
        "promotion": promotion_response,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    payload = result.get("promotion") or {}
    promoted = (
        ((payload.get("data") or {}).get("promoted"))
        if isinstance(payload, dict)
        else None
    )
    print(f"Agent replay nightly completed. promoted={promoted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
