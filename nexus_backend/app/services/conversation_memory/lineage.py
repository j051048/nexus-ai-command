"""Reject derived insights unless every original source is still valid and unchanged."""

import hashlib
import json
import logging
from typing import Any

from .governance import filter_current_memories, memory_is_current
from .visibility import apply_owner_scope

logger = logging.getLogger(__name__)
_CONTENT_FIELDS = (
    "id",
    "user_id",
    "organization_id",
    "category",
    "key",
    "value",
    "enriched_value",
    "version",
    "visibility",
    "lifecycle_state",
    "sensitivity",
    "expires_at",
    "valid_until",
    "superseded_by",
    "evidence_ref",
    "metadata",
    "provenance",
)


def source_fingerprint(memory: dict) -> str:
    payload = {key: memory.get(key) for key in _CONTENT_FIELDS}
    encoded = json.dumps(
        payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def source_snapshot(memories: list[dict]) -> dict[str, str]:
    return {str(row["id"]): source_fingerprint(row) for row in memories}


async def filter_valid_consolidations(
    rows: list[dict], *, user_id: str, org_id: str | None, db: Any
) -> list[dict]:
    candidates = [
        row
        for row in rows
        if row.get("user_id") == user_id
        and row.get("organization_id") == org_id
        and memory_is_current(row)
        and not row.get("invalidated_at")
        and isinstance(row.get("source_memory_ids"), list)
        and isinstance(row.get("source_fingerprints"), dict)
        and all(
            isinstance(value, str) and len(value) == 64
            for value in row["source_fingerprints"].values()
        )
        and 0 < len(row["source_memory_ids"]) <= 100
        and set(map(str, row["source_memory_ids"])) == set(row["source_fingerprints"])
    ]
    ids = sorted(
        {str(source) for row in candidates for source in row["source_memory_ids"]}
    )
    if not ids or len(ids) > 500:
        return []
    result = await apply_owner_scope(
        db.table("conversation_memories").select("*").in_("id", ids),
        user_id,
        org_id,
    ).execute()
    current = source_snapshot(
        filter_current_memories(result.data or [], user_id=user_id, org_id=org_id)
    )
    return [
        row
        for row in candidates
        if all(
            current.get(str(source)) == row["source_fingerprints"].get(str(source))
            for source in row["source_memory_ids"]
        )
    ]
