"""Run the golden contract against recorded JSON/JSONL model outputs."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "nexus_backend"
sys.path.insert(0, str(BACKEND))

from app.services.artifact_output_eval_service import evaluate_artifact_output_run


def _load_outputs(path: Path) -> list[dict]:
    content = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in content.splitlines() if line.strip()]
    parsed = json.loads(content)
    return parsed.get("outputs", parsed) if isinstance(parsed, dict) else parsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("outputs", type=Path, help="Recorded output JSON or JSONL")
    args = parser.parse_args()
    golden = json.loads(
        (BACKEND / "evals/datasets/artifact_delivery_golden.json").read_text(
            encoding="utf-8"
        )
    )
    report = evaluate_artifact_output_run(golden["cases"], _load_outputs(args.outputs))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["pass_rate"] >= float(golden["minimum_pass_rate"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
