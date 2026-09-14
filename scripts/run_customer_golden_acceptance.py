"""Run upload -> ingestion -> artifact job -> DOCX/PDF download against a live stack."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "nexus_backend"
MANIFEST = BACKEND / "evals/datasets/customer_delivery_acceptance.json"
FIXTURES = BACKEND / "evals/fixtures/customer_acceptance"


def _unwrap(response: httpx.Response) -> Any:
    response.raise_for_status()
    payload = response.json()
    outer = payload.get("data", payload)
    return outer.get("data", outer) if isinstance(outer, dict) else outer


def _validate_download(
    content: bytes, output_format: str, minimum: int, case: dict[str, Any]
) -> dict[str, Any]:
    if len(content) < minimum:
        raise AssertionError(f"{output_format} too small: {len(content)} bytes")
    # Reuse the production byte-level parser; a ZIP/PDF signature is not quality.
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    from app.services.artifact_export_validation import validate_export

    result = validate_export(
        content,
        output_format,
        title=case["title"],
        minimum_characters=int(case["minimum_character_count"]),
        required_terms=case["required_terms"],
        forbidden_terms=case.get("forbidden_terms", []),
        minimum_headings=int(case.get("minimum_headings", 3)),
        minimum_tables=int(case.get("minimum_tables", 1)),
    )
    return {
        **result,
        "format": output_format,
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


async def _verify_identity(client: httpx.AsyncClient, org_id: str) -> None:
    profile = _unwrap(await client.get("/api/users/profile"))
    user = profile.get("user") or {}
    if not user.get("id") or str(user.get("organization_id") or "") != org_id:
        raise ValueError(
            "Acceptance token does not belong to the requested organization"
        )


async def _poll(
    client: httpx.AsyncClient,
    path: str,
    *,
    terminal: set[str],
    timeout_seconds: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        data = _unwrap(await client.get(path))
        if str(data.get("status") or "") in terminal:
            return dict(data)
        await asyncio.sleep(2)
    raise TimeoutError(f"Timed out polling {path}")


async def run_case(client: httpx.AsyncClient, case: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    fixture_path = FIXTURES / case["fixture"]
    with fixture_path.open("rb") as handle:
        upload = await client.post(
            "/api/documents/upload",
            files={"files": (fixture_path.name, handle, "text/markdown")},
            data={"category": case["category"], "visibility": "organization"},
        )
    upload_data = _unwrap(upload)
    result = upload_data["results"][0]
    if result.get("status") == "duplicate":
        document_id = result["existing_document_id"]
    else:
        document_id = result["document_id"]
    ingestion = await _poll(
        client,
        f"/api/documents/{document_id}/ingestion",
        terminal={"ready", "completed", "error", "failed"},
        timeout_seconds=600,
    )
    if ingestion["status"] not in {"ready", "completed"}:
        raise AssertionError(f"knowledge ingestion failed: {ingestion}")

    job = _unwrap(
        await client.post(
            "/api/artifacts/jobs",
            json={
                "original_request": case["request"],
                "source_content": "",
                "title": case["title"],
                "artifact_type": case["artifact_type"],
                "audience": "customer",
                "requested_formats": case["formats"],
                "customer_context": {"instrument_line": case["instrument_line"]},
                "selected_document_ids": [document_id],
                "generation_mode": "deep",
                "target_character_count": int(case["minimum_character_count"]),
                "review_confirmed": False,
                "request_key": f"golden-{case['id']}-{uuid4()}",
            },
        )
    )
    final_job = await _poll(
        client,
        f"/api/artifacts/jobs/{job['id']}",
        terminal={"completed", "failed", "cancelled"},
        timeout_seconds=900,
    )
    if final_job["status"] != "completed":
        raise AssertionError(f"artifact generation failed: {final_job}")
    artifact_id = final_job.get("artifact_id") or final_job.get("result", {}).get("id")
    if not artifact_id:
        raise AssertionError("Completed job has no artifact ID")
    artifact = _unwrap(await client.get(f"/api/artifacts/{artifact_id}"))
    failures = []
    if not (artifact.get("quality") or {}).get("ready"):
        failures.append("artifact_not_quality_ready")
    if int((artifact.get("evidence") or {}).get("count") or 0) < 1:
        failures.append("evidence_missing")
    downloads = []
    for output_format in case["formats"]:
        response = await client.get(
            f"/api/artifacts/{artifact_id}/download",
            params={"format": output_format},
        )
        response.raise_for_status()
        validation = _validate_download(
            response.content, output_format, int(case["minimum_download_bytes"]), case
        )
        downloads.append(validation)
        failures.extend(f"{output_format}:{error}" for error in validation["errors"])
    return {
        "case_id": case["id"],
        "passed": not failures,
        "artifact_id": artifact_id,
        "job_id": job["id"],
        "document_id": document_id,
        "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "latency_ms": round((time.monotonic() - started) * 1000),
        "failures": failures,
        "downloads": downloads,
        "quality": artifact.get("quality"),
        "evidence": artifact.get("evidence"),
    }


async def async_main(require_live: bool, output: Path | None = None) -> int:
    base_url = os.getenv("GOLDEN_ACCEPTANCE_BASE_URL", "").strip()
    token = os.getenv("GOLDEN_ACCEPTANCE_TOKEN", "").strip()
    org_id = os.getenv("GOLDEN_ACCEPTANCE_ORG_ID", "").strip()
    if not base_url or not token or not org_id:
        if require_live:
            print("Live golden acceptance credentials are required")
            return 2
        print("SKIP live golden acceptance: credentials are not configured")
        return 0

    # Keep the static contract path dependency-free. Nightly jobs without live
    # credentials should not need the HTTP client used by the live acceptance run.
    import httpx

    headers = {"Authorization": f"Bearer {token}", "X-Org-ID": org_id}
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    results = []
    async with httpx.AsyncClient(
        base_url=base_url.rstrip("/"), headers=headers, timeout=180.0
    ) as client:
        # Headers are only hints; verify server-resolved identity before any upload.
        await _verify_identity(client, org_id)
        for case in manifest["cases"]:
            try:
                results.append(await run_case(client, case))
            except Exception as exc:
                results.append(
                    {"case_id": case["id"], "passed": False, "error": str(exc)}
                )
    passed = sum(int(item["passed"]) for item in results)
    pass_rate = passed / len(results) if results else 0
    report = {
        "schema_version": "customer-delivery-run.v2",
        "mode": "live",
        "completed_at": datetime.now(UTC).isoformat(),
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "pass_rate": pass_rate,
        "results": results,
    }
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    print(serialized)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized + "\n", encoding="utf-8")
    return 0 if pass_rate >= float(manifest["minimum_pass_rate"]) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-live", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    return asyncio.run(async_main(args.require_live, args.output))


if __name__ == "__main__":
    raise SystemExit(main())
