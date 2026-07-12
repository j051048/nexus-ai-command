"""Fail CI when runtime code hard-codes an expensive chat model."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "nexus_backend" / "app"
EXPENSIVE_MARKERS = (
    "gemini",
    "gpt-4",
    "gpt-5",
    "claude-opus",
    "claude-3-opus",
    "o3",
    "o4",
)
MODEL_KEYWORDS = {"model", "model_code", "model_name"}
ALLOWLIST = {
    "core/config.py",
    "core/model_pricing.py",
    "routers/llm/marketplace.py",
    "services/agent_operational_hardening.py",
    "services/agent_loop_engineering_service.py",
    "services/agent_slo_cost_service.py",
}


def _literal(value: ast.AST) -> str | None:
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def main() -> int:
    failures: list[str] = []
    for path in APP.rglob("*.py"):
        relative = path.relative_to(APP).as_posix()
        if relative in ALLOWLIST:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            failures.append(f"{relative}: cannot parse for model audit: {exc}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg not in MODEL_KEYWORDS:
                    continue
                value = (_literal(keyword.value) or "").lower()
                if any(marker in value for marker in EXPENSIVE_MARKERS):
                    failures.append(
                        f"{relative}:{node.lineno}: hard-coded expensive model {value!r}"
                    )

    if failures:
        print("LLM_COST_POLICY_FAIL")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("LLM_COST_POLICY_OK: no expensive runtime chat model literals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
