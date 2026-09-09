"""File-based release evaluation; synthetic checks never imply customer proof."""

import hashlib
from pathlib import Path

from app.services.artifact_export_validation import validate_export

EVALUATOR_VERSION = "delivery-release.v1"
FAMILIES = (
    "spectroscopy",
    "chromatography",
    "mass_spectrometry",
    "energy_spectroscopy",
    "electronic_instruments",
)
SCENARIOS = (
    "customer_solution",
    "tender_response",
    "competitor_brief",
    "service_terms",
    "budget_alternative",
)


def synthetic_case_catalog():
    return [
        {
            "id": f"{family}-{scenario}",
            "family": family,
            "scenario": scenario,
            "origin": "synthetic",
            "required_terms": ["以双方确认的验收方法为准"],
            "forbidden_terms": ["保证百分之百中标"],
            "minimum_characters": 600,
        }
        for family in FAMILIES
        for scenario in SCENARIOS
    ]


def evaluate_release(manifest, base_dir, *, require_customer_proof=False):
    base = Path(base_dir).resolve()
    errors = []
    results = []
    cases = manifest.get("cases") or []
    identities = [case.get("id") for case in cases]
    if not cases or len(set(identities)) != len(cases) or not all(identities):
        errors.append("missing_or_duplicate_cases")
    provenance = manifest.get("provenance") or {}
    if not all(
        provenance.get(key)
        for key in (
            "git_commit",
            "pipeline_version",
            "model",
            "template_version",
            "dataset_version",
        )
    ):
        errors.append("release_provenance_incomplete")
    if require_customer_proof:
        if len(cases) < 25 or not set(FAMILIES) <= {
            case.get("family") for case in cases
        }:
            errors.append("customer_coverage_incomplete")
    for case in cases:
        case_errors = []
        review = case.get("review") or {}
        if require_customer_proof and (
            case.get("origin") != "customer_authorized"
            or review.get("approved") is not True
            or not review.get("reviewer")
            or not review.get("reviewed_at")
            or not case.get("consent_reference")
        ):
            case_errors.append("customer_review_missing")
        filename = case.get("file")
        if not isinstance(filename, str) or not filename:
            results.append(
                {"id": case.get("id"), "ok": False, "errors": ["file_missing"]}
            )
            continue
        path = (base / filename).resolve()
        if not path.is_relative_to(base) or not path.is_file():
            results.append(
                {
                    "id": case.get("id"),
                    "ok": False,
                    "errors": ["file_outside_manifest_or_missing"],
                }
            )
            continue
        if path.stat().st_size > 50_000_000:
            results.append(
                {"id": case.get("id"), "ok": False, "errors": ["file_too_large"]}
            )
            continue
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if require_customer_proof and review.get("file_sha256") != digest:
            case_errors.append("review_does_not_match_export")
        if (
            not case.get("title")
            or not case.get("required_terms")
            or not case.get("minimum_characters")
        ):
            case_errors.append("acceptance_criteria_missing")
        inspection = validate_export(
            content,
            path.suffix.lstrip("."),
            title=case.get("title") or "",
            minimum_characters=max(0, int(case.get("minimum_characters") or 0)),
            required_terms=case.get("required_terms") or [],
            forbidden_terms=case.get("forbidden_terms") or [],
        )
        results.append(
            {
                "id": case.get("id"),
                "sha256": digest,
                "origin": case.get("origin"),
                "ok": inspection["ok"] and not case_errors,
                "errors": [*case_errors, *inspection["errors"]],
                "inspection": inspection,
            }
        )
    return {
        "evaluator": EVALUATOR_VERSION,
        "provenance": provenance,
        "mode": "customer_proof" if require_customer_proof else "export_regression",
        "ok": not errors and bool(results) and all(row["ok"] for row in results),
        "errors": errors,
        "cases": results,
    }
