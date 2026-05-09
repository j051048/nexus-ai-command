"""Static prompt manifest drift check.

Fails when the frontend reintroduces backend prompt mirrors or when backend
runtime prompts contain mojibake markers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "nexus_backend"
sys.path.insert(0, str(BACKEND))


def main() -> int:
    from app.core.prompts_registry import get_prompt_manifest, SYSTEM_PROMPTS
    from app.agent.context_ledger import MOJIBAKE_MARKERS

    manifest = get_prompt_manifest()
    frontend = (ROOT / "src/services/agentPrompts.ts").read_text(encoding="utf-8")
    failures: list[str] = []

    if "SECURITY_GUARDRAILS = `" in frontend or "SYSTEM_PROMPTS:" in frontend:
        failures.append("frontend appears to mirror backend prompt bodies")
    if "minimal_read_only_fallback" not in json.dumps(
        manifest.get("frontend_policy", {}), ensure_ascii=False
    ):
        failures.append("manifest frontend policy is missing read-only fallback marker")

    for key, text in SYSTEM_PROMPTS.items():
        if any(marker in text for marker in MOJIBAKE_MARKERS):
            failures.append(f"system prompt '{key}' contains mojibake markers")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print(f"OK prompt manifest {manifest['manifest_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
