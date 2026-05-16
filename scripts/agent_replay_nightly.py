"""Nightly Agent replay promotion and health runner.

When AGENT_REPLAY_BASE_URL and AGENT_REPLAY_TOKEN are configured, this script
calls the production/staging replay API to promote recent failures into eval
cases. Without credentials it performs static readiness checks so scheduled CI
still guards against accidental removal of the replay harness.
"""

from __future__ import annotations

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


def static_check() -> int:
    missing = [path for path in STATIC_REPLAY_FILES if not (ROOT / path).exists()]
    if missing:
        print("Agent replay static check failed:")
        for path in missing:
            print(f" - missing {path}")
        return 1
    router = (ROOT / "nexus_backend/app/routers/agent_replay.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    required_tokens = [
        "/eval-cases/promote-failures",
        "/eval-cases",
        "compare_sessions",
        "get_checkpoint_history",
    ]
    missing_tokens = [token for token in required_tokens if token not in router]
    if missing_tokens:
        print("Agent replay static check failed:")
        for token in missing_tokens:
            print(f" - missing token {token}")
        return 1
    print("Agent replay static harness present. Set AGENT_REPLAY_BASE_URL and AGENT_REPLAY_TOKEN to execute remotely.")
    return 0


def post_json(url: str, token: str) -> dict:
    request = urllib.request.Request(
        url,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        data=b"{}",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8")
        return json.loads(payload) if payload else {}


def main() -> int:
    base_url = os.getenv("AGENT_REPLAY_BASE_URL", "").rstrip("/")
    token = os.getenv("AGENT_REPLAY_TOKEN", "")
    if not base_url or not token:
        return static_check()

    endpoint = f"{base_url}/api/agent/replay/eval-cases/promote-failures?limit=50"
    try:
        result = post_json(endpoint, token)
    except urllib.error.HTTPError as exc:
        print(f"Agent replay promotion failed: HTTP {exc.code}", file=sys.stderr)
        print(exc.read().decode("utf-8", errors="replace")[:1000], file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Agent replay promotion failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    promoted = ((result.get("data") or {}).get("promoted")) if isinstance(result, dict) else None
    print(f"Agent replay nightly completed. promoted={promoted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
