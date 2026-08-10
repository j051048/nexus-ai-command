"""Run upload -> ingestion -> artifact job -> DOCX/PDF download against a live stack."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

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


def _validate_download(content: bytes, output_format: str, minimum: int) -> None:
    if len(content) < minimum:
        raise AssertionError(f"{output_format} too small: {len(content)} bytes")
    if output_format == "pdf" and not content.startswith(b"%PDF"):
        raise AssertionError("PDF signature missing")
    if output_format == "docx":
        if not zipfile.is_zipfile(BytesIO(content)):
            raise AssertionError("DOCX is not a valid ZIP package")
        with zipfile.ZipFile(BytesIO(content)) as archive:
            if "word/document.xml" not in archive.namelist():
                raise AssertionError("DOCX document body missing")


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
                "review_confirmed": False,
                "request_key": f"golden-{case['id']}-{int(time.time())}",
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
    for output_format in case["formats"]:
        response = await client.get(
            f"/api/artifacts/{artifact_id}/download",
            params={"format": output_format},
        )
        response.raise_for_status()
        _validate_download(
            response.content, output_format, int(case["minimum_download_bytes"])
        )
    return {"case_id": case["id"], "passed": True, "artifact_id": artifact_id}


async def async_main(require_live: bool) -> int:
    base_url = os.getenv("GOLDEN_ACCEPTANCE_BASE_URL", "").strip()
    token = os.getenv("GOLDEN_ACCEPTANCE_TOKEN", "").strip()
    if not base_url or not token:
        if require_live:
            print("Live golden acceptance credentials are required")
            return 2
        print("SKIP live golden acceptance: credentials are not configured")
        return 0
    headers = {"Authorization": f"Bearer {token}"}
    org_id = os.getenv("GOLDEN_ACCEPTANCE_ORG_ID", "").strip()
    if org_id:
        headers["X-Organization-ID"] = org_id
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    results = []
    async with httpx.AsyncClient(
        base_url=base_url.rstrip("/"), headers=headers, timeout=180.0
    ) as client:
        for case in manifest["cases"]:
            try:
                results.append(await run_case(client, case))
            except Exception as exc:
                results.append(
                    {"case_id": case["id"], "passed": False, "error": str(exc)}
                )
    passed = sum(int(item["passed"]) for item in results)
    pass_rate = passed / len(results) if results else 0
    print(
        json.dumps(
            {"pass_rate": pass_rate, "results": results}, ensure_ascii=False, indent=2
        )
    )
    return 0 if pass_rate >= float(manifest["minimum_pass_rate"]) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-live", action="store_true")
    args = parser.parse_args()
    return asyncio.run(async_main(args.require_live))


if __name__ == "__main__":
    raise SystemExit(main())
