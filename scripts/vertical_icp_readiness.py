"""Evaluate anonymized scientific-instrument ICP evidence from a JSON file."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "nexus_backend"
sys.path.insert(0, str(BACKEND))

from app.services.vertical_icp_validation_service import (  # noqa: E402
    evaluate_vertical_readiness,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path, help="JSON array of anonymized evidence")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero until the discovery gate is supported",
    )
    args = parser.parse_args()

    rows = json.loads(args.evidence.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Evidence file must contain a JSON array")

    result = evaluate_vertical_readiness(rows)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if args.strict and not result["discovery_ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
