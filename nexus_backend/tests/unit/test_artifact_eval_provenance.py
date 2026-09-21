"""Artifact-quality evidence must not overstate what it proves.

The product advertises 一次通过率 >= 90% / 平均分 >= 85. Those numbers are only
meaningful if the recording behind them came from the real pipeline, so the
gate has to refuse both a relabelled fixture and a live baseline that lost its
provenance.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.artifact_eval_provenance import load_artifact_eval_provenance
from app.services.artifact_output_recorder import (
    LIVE_SOURCE,
    PROMPT_ONLY_SOURCE,
    build_manifest,
    build_record,
    live_evidence_problems,
    recording_sha256,
    validate_records,
    write_recording,
)
from scripts.check_artifact_eval_provenance import check

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


def _fixture_baseline() -> dict:
    return {
        "version": 1,
        "source": "contract-fixture",
        "recorded_at": NOW.isoformat(),
        "pass_rate": 1.0,
        "minimum_pass_rate": 0.9,
        "models": ["contract-fixture"],
        "cases": {"case-a": True, "case-b": True},
    }


def _live_baseline(**overrides) -> dict:
    baseline = {
        "version": 2,
        "source": LIVE_SOURCE,
        "recorded_at": NOW.isoformat(),
        "pass_rate": 1.0,
        "minimum_pass_rate": 0.9,
        "models": ["deepseek-v4.1-flash"],
        "cases": {"case-a": True},
        "recorded_outputs_sha256": "a" * 64,
        "environment": "staging",
        "evidence_document_ids": ["doc-1"],
    }
    baseline.update(overrides)
    return baseline


def test_committed_baseline_is_honest_today() -> None:
    # The shipped baseline is a fixture: it must pass the consistency check and
    # must be refused by the release profile, which is the honest state.
    baseline = json.loads(
        (ROOT / "nexus_backend/evals/artifact_output_baseline.json").read_text(
            encoding="utf-8"
        )
    )

    assert check(baseline, now=NOW) == []
    assert check(baseline, require_live=True, now=NOW) == [
        "live_baseline_required_but_source_is:contract-fixture"
    ]


def test_fixture_baseline_passes_and_live_requirement_fails() -> None:
    assert check(_fixture_baseline(), now=NOW) == []
    failures = check(_fixture_baseline(), require_live=True, now=NOW)
    assert "live_baseline_required_but_source_is:contract-fixture" in failures


def test_complete_live_baseline_passes_both_modes() -> None:
    assert check(_live_baseline(), now=NOW) == []
    assert check(_live_baseline(), require_live=True, now=NOW) == []


@pytest.mark.parametrize(
    "missing",
    ["recorded_outputs_sha256", "environment", "evidence_document_ids"],
)
def test_live_baseline_without_provenance_is_refused(missing: str) -> None:
    failures = check(_live_baseline(**{missing: None}), now=NOW)

    assert f"live_baseline_missing:{missing}" in failures


def test_live_baseline_goes_stale() -> None:
    failures = check(
        _live_baseline(recorded_at=(NOW - timedelta(days=400)).isoformat()), now=NOW
    )

    assert any(item.startswith("live_baseline_stale:") for item in failures)


def test_fixture_carrying_live_evidence_is_inconsistent() -> None:
    baseline = _fixture_baseline()
    baseline["evidence_document_ids"] = ["doc-1"]

    failures = check(baseline, now=NOW)

    assert "fixture_baseline_carries_live_evidence:evidence_document_ids" in failures


def test_unknown_model_and_failing_cases_are_refused() -> None:
    failures = check(
        _live_baseline(models=["unknown"], cases={"case-a": True, "case-b": False}),
        now=NOW,
    )

    assert "unknown_model" in failures
    assert "cases_not_passing:case-b" in failures


def test_provenance_helper_reads_the_baseline(tmp_path) -> None:
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(_live_baseline()), encoding="utf-8")

    provenance = load_artifact_eval_provenance(path)

    assert provenance["available"] is True
    assert provenance["claims_live_quality"] is True
    assert provenance["evidence_documents"] == ["doc-1"]


def test_provenance_helper_reports_missing_baseline(tmp_path) -> None:
    provenance = load_artifact_eval_provenance(tmp_path / "missing.json")

    assert provenance["available"] is False
    assert provenance["claims_live_quality"] is False


def test_recorder_requires_model_latency_and_cost() -> None:
    records = [
        build_record(
            case_id="case-a",
            content="正文 [EVID:doc:1]",
            model=None,
            latency_ms=None,
            cost_usd=None,
        )
    ]

    problems = validate_records(records, ["case-a"])

    assert "missing_model:case-a" in problems
    assert "missing_latency_ms:case-a" in problems
    assert "missing_cost_usd:case-a" in problems


def test_recorder_detects_missing_and_duplicate_cases() -> None:
    record = build_record(
        case_id="case-a",
        content="正文",
        model="m",
        latency_ms=1.0,
        cost_usd=0.01,
    )

    problems = validate_records([record, dict(record)], ["case-a", "case-b"])

    assert "missing_cases:case-b" in problems
    assert "duplicate_case_ids" in problems


def test_prompt_only_recording_cannot_be_live_evidence(tmp_path) -> None:
    records = [
        build_record(
            case_id="case-a",
            content="摘要",
            model="deepseek-v4.1-flash",
            latency_ms=1200.0,
            cost_usd=0.02,
        )
    ]
    manifest = build_manifest(
        source=PROMPT_ONLY_SOURCE,
        records=records,
        dataset_path="nexus_backend/evals/datasets/artifact_delivery_golden.json",
        environment="staging",
        evidence_document_ids=[],
    )

    problems = live_evidence_problems(records, manifest, ["case-a"])

    assert f"manifest_source:{PROMPT_ONLY_SOURCE}" in problems
    assert "manifest_evidence_missing" in problems


def test_full_live_recording_round_trip(tmp_path) -> None:
    records = [
        build_record(
            case_id="case-a",
            content="正文 [EVID:doc:1]",
            model="deepseek-v4.1-flash",
            latency_ms=2450.0,
            cost_usd=0.031,
        ),
        build_record(
            case_id="case-b",
            content="正文 [EVID:doc:2]",
            model="deepseek-v4.1-flash",
            latency_ms=1900.0,
            cost_usd=0.028,
        ),
    ]
    manifest = build_manifest(
        source=LIVE_SOURCE,
        records=records,
        dataset_path="nexus_backend/evals/datasets/artifact_delivery_golden.json",
        environment="staging",
        evidence_document_ids=["doc-1", "doc-2"],
        git_sha="abc1234",
    )
    output = tmp_path / "live.jsonl"

    manifest_path = write_recording(
        output_path=output, records=records, manifest=manifest
    )

    assert manifest_path.exists()
    assert manifest["records_sha256"] == recording_sha256(records)
    assert live_evidence_problems(records, manifest, ["case-a", "case-b"]) == []
