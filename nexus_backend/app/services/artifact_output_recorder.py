"""Record real-model artifact outputs as evidence for the quality baseline.

The artifact eval contract can be satisfied by hand-written fixtures, which is
why the committed baseline says ``contract-fixture``: those outputs prove the
evaluator works, not that the product writes good documents. This module turns
a real generation run into a recording that carries the provenance needed to
claim model quality:

* ``model`` - which model produced the document;
* ``latency_ms`` / ``cost_usd`` - what the run actually cost;
* a manifest with the dataset hash, environment, evidence document ids and the
  sha256 of the recorded outputs.

``validate_records`` is the honesty gate: a recording missing any of those
fields cannot be labelled ``live-model``, so a fixture can never be relabelled
as real-model evidence.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LIVE_SOURCE = "live-model"
PROMPT_ONLY_SOURCE = "prompt-only"
FIXTURE_SOURCE = "contract-fixture"

#: Fields a record must carry before it may be called live-model evidence.
REQUIRED_RECORD_FIELDS = ("case_id", "model", "latency_ms", "cost_usd")


def build_record(
    *,
    case_id: str,
    content: str,
    model: str | None,
    latency_ms: float | None,
    cost_usd: float | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "case_id": str(case_id),
        "content": content,
        "model": model,
        "latency_ms": None if latency_ms is None else round(float(latency_ms), 2),
        "cost_usd": None if cost_usd is None else round(float(cost_usd), 6),
    }
    record.update(extra or {})
    return record


def recording_sha256(records: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(
            json.dumps(record, sort_keys=True, ensure_ascii=False, default=str).encode(
                "utf-8"
            )
        )
        digest.update(b"\n")
    return digest.hexdigest()


def validate_records(
    records: list[dict[str, Any]], expected_case_ids: list[str]
) -> list[str]:
    """Return the reasons this recording cannot be used as live evidence."""
    problems: list[str] = []
    seen = {str(record.get("case_id")) for record in records}
    missing_cases = [case for case in expected_case_ids if case not in seen]
    if missing_cases:
        problems.append("missing_cases:" + ",".join(missing_cases))
    if len(seen) != len(records):
        problems.append("duplicate_case_ids")

    for record in records:
        case_id = str(record.get("case_id"))
        for field in REQUIRED_RECORD_FIELDS:
            value = record.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                problems.append(f"missing_{field}:{case_id}")
        if not str(record.get("content") or "").strip():
            problems.append(f"empty_content:{case_id}")
    unknown_models = [
        str(record.get("case_id"))
        for record in records
        if str(record.get("model") or "").strip().lower() in {"", "unknown"}
    ]
    if unknown_models:
        problems.append("unknown_model:" + ",".join(unknown_models))
    return problems


def build_manifest(
    *,
    source: str,
    records: list[dict[str, Any]],
    dataset_path: str,
    environment: str | None,
    evidence_document_ids: list[str] | None = None,
    git_sha: str | None = None,
    orchestration_version: str | None = None,
) -> dict[str, Any]:
    models = sorted(
        {str(record.get("model")) for record in records if record.get("model")}
    )
    return {
        "source": source,
        "recorded_at": datetime.now(UTC).isoformat(),
        "dataset": dataset_path,
        "case_count": len(records),
        "models": models,
        "environment": environment,
        "evidence_document_ids": list(evidence_document_ids or []),
        "git_sha": git_sha,
        "orchestration_version": orchestration_version,
        "totals": {
            "latency_ms": round(
                sum(float(record["latency_ms"]) for record in records), 2
            ),
            "cost_usd": round(sum(float(record["cost_usd"]) for record in records), 6),
        },
        "records_sha256": recording_sha256(records),
    }


def write_recording(
    *,
    output_path: Path,
    records: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> Path:
    """Write ``<output>.jsonl`` plus a ``<output>.manifest.json`` sidecar."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(
            json.dumps(record, ensure_ascii=False, default=str) for record in records
        )
        + "\n",
        encoding="utf-8",
    )
    manifest_path = output_path.with_suffix(output_path.suffix + ".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest_path


def load_recording(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Load recorded outputs and, when present, the provenance sidecar."""
    content = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        records = [json.loads(line) for line in content.splitlines() if line.strip()]
    else:
        parsed = json.loads(content)
        records = parsed.get("outputs", parsed) if isinstance(parsed, dict) else parsed
    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    if not manifest_path.exists():
        return records, None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("[ArtifactRecorder] manifest unreadable: %s", exc)
        return records, None
    return records, manifest


def live_evidence_problems(
    records: list[dict[str, Any]],
    manifest: dict[str, Any] | None,
    expected_case_ids: list[str],
) -> list[str]:
    """Everything that must hold before a recording may be called live-model."""
    problems = validate_records(records, expected_case_ids)
    if manifest is None:
        problems.append("manifest_missing")
        return problems
    if str(manifest.get("source") or "") != LIVE_SOURCE:
        problems.append(f"manifest_source:{manifest.get('source')}")
    if not manifest.get("evidence_document_ids"):
        # Live documents must be grounded in real evidence; without it the run
        # cannot show that citations and parameters come from customer data.
        problems.append("manifest_evidence_missing")
    if not manifest.get("environment"):
        problems.append("manifest_environment_missing")
    if not manifest.get("records_sha256"):
        problems.append("manifest_records_sha256_missing")
    return problems
