"""Record real-model artifact outputs for the quality baseline.

The committed baseline is ``contract-fixture``: it proves the evaluator works.
To claim real document quality the product needs a recording produced by the
real generation pipeline, with the model id, latency, cost and the evidence
documents it was grounded in. That is what this script writes.

Two modes:

* ``--from-pipeline`` (default) - runs golden cases through
  ``generate_artifact`` against a real Supabase project, then records the
  persisted Markdown plus provenance. This creates documents in that project,
  so it needs ``--confirm-live`` and refuses to run against ``ENV=production``
  unless ``--allow-production`` is passed deliberately.
* ``--smoke`` - one DB-free call through the configured model gateway, to check
  credentials and latency before a real recording. It cannot produce live
  evidence (no evidence documents), so it is never usable as a baseline.

Usage::

    python scripts/record_artifact_outputs.py --smoke
    python scripts/record_artifact_outputs.py --from-pipeline --confirm-live \
        --organization-id <uuid> --user-id <uuid> --document-ids <doc-uuid>[,...]
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "nexus_backend"
sys.path.insert(0, str(BACKEND))

GOLDEN = BACKEND / "evals/datasets/artifact_delivery_golden.json"
DEFAULT_OUTPUT = BACKEND / "evals/recorded/live-model.jsonl"

from app.services.artifact_output_recorder import (  # noqa: E402
    LIVE_SOURCE,
    PROMPT_ONLY_SOURCE,
    build_manifest,
    build_record,
    validate_records,
    write_recording,
)


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _load_cases() -> list[dict]:
    payload = json.loads(GOLDEN.read_text(encoding="utf-8"))
    return payload["cases"]


def _selected(cases: list[dict], only: str | None) -> list[dict]:
    if not only:
        return cases
    wanted = {item.strip() for item in only.split(",") if item.strip()}
    known = {str(case.get("id")) for case in cases}
    unknown = wanted - known
    if unknown:
        raise SystemExit(f"unknown case ids: {', '.join(sorted(unknown))}")
    return [case for case in cases if str(case.get("id")) in wanted]


async def _record_from_pipeline(args, cases: list[dict]) -> list[dict]:
    from app.core.config import settings
    from app.core.database import supabase
    from app.services.artifact_generation_service import generate_artifact
    from app.services.artifact_workspace_service import load_artifact_snapshot

    if not supabase:
        raise SystemExit("SUPABASE_URL/SUPABASE_SERVICE_KEY are required")
    environment = str(settings.ENV)
    if environment == "production" and not args.allow_production:
        raise SystemExit(
            "refusing to create artifacts in production; pass --allow-production "
            "only if this project is the intended recording target"
        )

    document_ids = [
        item.strip() for item in (args.document_ids or "").split(",") if item.strip()
    ]
    if not document_ids:
        raise SystemExit(
            "--document-ids is required: live evidence must be grounded in real "
            "customer documents, otherwise the recording cannot back a quality claim"
        )

    records: list[dict] = []
    for case in cases:
        started = time.perf_counter()
        result = await generate_artifact(
            db=supabase,
            organization_id=args.organization_id,
            user_id=args.user_id,
            original_request=str(case["request"]),
            source_content="",
            artifact_type=case.get("artifact_type"),
            customer_context={"instrument_line": case.get("instrument_line")},
            selected_document_ids=document_ids,
            generation_mode="deep",
        )
        latency_ms = (time.perf_counter() - started) * 1000
        _, version = await load_artifact_snapshot(
            supabase, args.organization_id, result.get("id")
        )
        metadata = version.get("generation_metadata") or {}
        usage = metadata.get("usage") or result.get("usage") or {}
        records.append(
            build_record(
                case_id=str(case["id"]),
                content=str(version.get("content_markdown") or ""),
                model=str(metadata.get("model") or ""),
                latency_ms=latency_ms,
                cost_usd=usage.get("call_cost"),
                extra={
                    "artifact_id": result.get("id"),
                    "quality_score": (result.get("quality") or {}).get("score"),
                    "evidence_count": (result.get("evidence") or {}).get("count"),
                },
            )
        )
        print(f"recorded {case['id']} latency={latency_ms:.0f}ms")
    return records


async def _smoke(case: dict) -> dict:
    from app.core.config import settings
    from app.services.llm_gateway import llm_gateway

    started = time.perf_counter()
    response = await llm_gateway.chat(
        scene_code="artifact_recording_smoke",
        agent_code="scientific_artifact_writer",
        user_id="recording-smoke",
        org_id=None,
        system_prompt="你是科学仪器企业的资深售前方案作者。只输出一段 120 字以内的中文摘要。",
        messages=[{"role": "user", "content": str(case["request"])}],
        temperature=0.2,
        max_tokens=400,
    )
    latency_ms = (time.perf_counter() - started) * 1000
    usage = getattr(response, "usage", None) or {}
    return build_record(
        case_id=str(case["id"]),
        content=str(getattr(response, "content", "") or ""),
        model=str(getattr(response, "model_code", "") or ""),
        latency_ms=latency_ms,
        cost_usd=usage.get("call_cost"),
        extra={"finish_reason": getattr(response, "finish_reason", None), "env": settings.ENV},
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-pipeline", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--allow-production", action="store_true")
    parser.add_argument("--organization-id")
    parser.add_argument("--user-id")
    parser.add_argument("--document-ids")
    parser.add_argument("--cases", help="Comma separated case ids")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    cases = _selected(_load_cases(), args.cases)

    if args.smoke:
        print(
            "note: smoke mode runs without an organization, so the gateway's "
            "quota/usage writes log uuid warnings; that is expected here."
        )
        record = asyncio.run(_smoke(cases[0]))
        print(json.dumps(record, ensure_ascii=False, indent=2))
        problems = validate_records([record], [str(cases[0]["id"])])
        if problems:
            print("SMOKE_RECORD_INCOMPLETE " + "; ".join(problems))
            return 1
        print("ARTIFACT_RECORDING_SMOKE_OK (not usable as a baseline)")
        return 0

    if not args.confirm_live:
        raise SystemExit(
            "--confirm-live is required: this mode creates real artifacts via the pipeline"
        )
    if not args.organization_id or not args.user_id:
        raise SystemExit("--organization-id and --user-id are required")

    from app.core.config import settings

    records = asyncio.run(_record_from_pipeline(args, cases))
    problems = validate_records(records, [str(case["id"]) for case in cases])
    if problems:
        print("ARTIFACT_RECORDING_INCOMPLETE " + "; ".join(problems))
        return 1

    manifest = build_manifest(
        source=LIVE_SOURCE,
        records=records,
        dataset_path=str(GOLDEN.relative_to(ROOT)).replace("\\", "/"),
        environment=str(settings.ENV),
        evidence_document_ids=[
            item.strip() for item in (args.document_ids or "").split(",") if item.strip()
        ],
        git_sha=_git_sha(),
    )
    manifest_path = write_recording(
        output_path=args.output, records=records, manifest=manifest
    )
    print(f"ARTIFACT_RECORDING_WRITTEN {args.output}")
    print(f"ARTIFACT_RECORDING_MANIFEST {manifest_path}")
    print(
        "next: python scripts/run_artifact_output_eval.py "
        f"{args.output} --label {LIVE_SOURCE} --update-baseline"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
