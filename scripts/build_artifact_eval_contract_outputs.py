"""Build deterministic seed outputs that exercise the artifact eval contract.

These are not claimed as live model evidence. Live customer-path proof is
performed by ``run_customer_golden_acceptance.py``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "nexus_backend/evals/datasets/artifact_delivery_golden.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    outputs = []
    for case in golden["cases"]:
        headings = "\n".join(f"## {title}\n" for title in case["expected_sections"])
        required = "、".join(case["required_terms"])
        paragraph = (
            f"本节基于已核验企业资料说明 {required} 的适用条件、验收方法、风险边界与下一步动作。"
            "所有参数均需回到原始记录复核，不以推断代替实测，并保留版本、责任人和日期。"
            "[EVID:contract-fixture:section-1]\n"
        )
        minimum = int(case["minimum_character_count"])
        repeat = max(1, minimum // max(1, len(paragraph)) + 2)
        outputs.append(
            {
                "case_id": case["id"],
                "content": headings + paragraph * repeat,
                "model": "contract-fixture",
                "latency_ms": 0,
                "cost_usd": 0,
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"outputs": outputs}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(outputs)} evaluator contract outputs to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
