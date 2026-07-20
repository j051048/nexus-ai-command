"""Cost and cache policy for solution generation."""

from __future__ import annotations

import hashlib
import json
from typing import Any

POLICY_VERSION = "solution-generation.v1"
MAX_EVIDENCE_ITEMS = 8
MAX_EVIDENCE_CHARS = 8_000
MAX_PRODUCTS = 30


def compact_generation_context(
    products: list[dict[str, Any]], evidence: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    compact_products = products[:MAX_PRODUCTS]
    remaining = MAX_EVIDENCE_CHARS
    compact_evidence: list[dict[str, Any]] = []
    for item in evidence[:MAX_EVIDENCE_ITEMS]:
        excerpt = str(item.get("excerpt") or "")[:remaining]
        if not excerpt and remaining <= 0:
            break
        compact_evidence.append({**item, "excerpt": excerpt})
        remaining -= len(excerpt)
    return compact_products, compact_evidence


def generation_fingerprint(
    brief: dict[str, Any],
    workspace: dict[str, Any],
    products: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> str:
    payload = {
        "policy": POLICY_VERSION,
        "brief": brief,
        "requirements": workspace.get("requirements") or [],
        "packages": workspace.get("packages") or [],
        "products": [
            {
                "model_code": item.get("model_code"),
                "revision": item.get("revision"),
                "validation_status": item.get("validation_status"),
            }
            for item in products
        ],
        "evidence": [
            {
                "document_id": item.get("document_id"),
                "source_version": item.get("source_version"),
                "score": item.get("score"),
            }
            for item in evidence
        ],
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, default=str
    ).encode()
    return hashlib.sha256(encoded).hexdigest()
