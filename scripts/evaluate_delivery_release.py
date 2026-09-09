"""Evaluate real exported files; run with the backend Python environment."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "nexus_backend"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--require-customer-proof", action="store_true")
    args = parser.parse_args()
    from app.services.delivery_release_eval import evaluate_release

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    report = evaluate_release(manifest, args.manifest.parent,
                              require_customer_proof=args.require_customer_proof)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
