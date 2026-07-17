"""Tenant-scoped read API for the organization knowledge graph."""

from __future__ import annotations

import base64
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.core.auth import get_current_org_id
from app.core.dependencies import get_request_db
from app.core.errors import api_success

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Graph"])

_MODERN_COLUMNS = (
    "id,source_entity,source_type,relationship,destination_entity,"
    "destination_type,confidence,source_context,created_at"
)
_LEGACY_COLUMNS = (
    "id,source,source_type,relationship,destination,destination_type,"
    "confidence,source_context,created_at"
)


def _entity_id(name: str, entity_type: str | None) -> str:
    payload = f"{entity_type or 'concept'}\0{name}".encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_entity_id(entity_id: str) -> tuple[str, str]:
    padding = "=" * (-len(entity_id) % 4)
    try:
        decoded = base64.urlsafe_b64decode(entity_id + padding).decode()
        entity_type, name = decoded.split("\0", 1)
        return name, entity_type
    except (ValueError, UnicodeDecodeError):
        return entity_id, "concept"


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "source_entity": row.get("source_entity") or row.get("source") or "",
        "destination_entity": row.get("destination_entity")
        or row.get("destination")
        or "",
        "source_type": row.get("source_type") or "concept",
        "destination_type": row.get("destination_type") or "concept",
        "confidence": float(row.get("confidence") or 0),
    }


async def _load_rows(
    db: Any,
    *,
    search: str | None = None,
    entity: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Read both current and legacy graph schemas during migration convergence."""
    schemas = (
        (_MODERN_COLUMNS, "source_entity", "destination_entity"),
        (_LEGACY_COLUMNS, "source", "destination"),
    )
    for columns, source_column, destination_column in schemas:
        try:
            if search:
                source_result = await (
                    db.table("knowledge_graph_triples")
                    .select(columns)
                    .ilike(source_column, f"%{search}%")
                    .limit(limit)
                    .execute()
                )
                destination_result = await (
                    db.table("knowledge_graph_triples")
                    .select(columns)
                    .ilike(destination_column, f"%{search}%")
                    .limit(limit)
                    .execute()
                )
                raw_rows = (source_result.data or []) + (destination_result.data or [])
            elif entity:
                source_result = await (
                    db.table("knowledge_graph_triples")
                    .select(columns)
                    .eq(source_column, entity)
                    .limit(limit)
                    .execute()
                )
                destination_result = await (
                    db.table("knowledge_graph_triples")
                    .select(columns)
                    .eq(destination_column, entity)
                    .limit(limit)
                    .execute()
                )
                raw_rows = (source_result.data or []) + (destination_result.data or [])
            else:
                result = await (
                    db.table("knowledge_graph_triples")
                    .select(columns)
                    .limit(limit)
                    .execute()
                )
                raw_rows = result.data or []

            deduplicated = {
                str(row.get("id") or index): row for index, row in enumerate(raw_rows)
            }
            return [_normalize_row(row) for row in deduplicated.values()]
        except Exception:
            continue
    return []


def _entity_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entities: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        for side in ("source", "destination"):
            name = row[f"{side}_entity"]
            entity_type = row[f"{side}_type"]
            if not name:
                continue
            key = (name, entity_type)
            record = entities.setdefault(
                key,
                {
                    "id": _entity_id(name, entity_type),
                    "name": name,
                    "entity_type": entity_type,
                    "properties": {},
                    "relation_count": 0,
                    "created_at": row.get("created_at") or "",
                },
            )
            record["relation_count"] += 1
    return sorted(
        entities.values(),
        key=lambda item: (-item["relation_count"], item["name"]),
    )


@router.get("/search")
async def search_entities(
    q: str = Query(min_length=1, max_length=100),
    db: Any = Depends(get_request_db),
    _organization_id: str = Depends(get_current_org_id),
):
    rows = await _load_rows(db, search=q.strip(), limit=100)
    return api_success(data=_entity_records(rows)[:50])


@router.get("/entity/{entity_id}/relations")
async def get_entity_relations(
    entity_id: str,
    db: Any = Depends(get_request_db),
    _organization_id: str = Depends(get_current_org_id),
):
    entity_name, _entity_type = _decode_entity_id(entity_id)
    rows = await _load_rows(db, entity=entity_name, limit=100)
    relations = [
        {
            "id": str(row.get("id") or ""),
            "source_id": _entity_id(row["source_entity"], row["source_type"]),
            "source_name": row["source_entity"],
            "target_id": _entity_id(row["destination_entity"], row["destination_type"]),
            "target_name": row["destination_entity"],
            "relation_type": row.get("relationship") or "related_to",
            "weight": row["confidence"],
            "properties": {"source_context": row.get("source_context") or ""},
        }
        for row in rows
    ]
    return api_success(data=relations)


@router.get("/patterns")
async def get_graph_patterns(
    db: Any = Depends(get_request_db),
    _organization_id: str = Depends(get_current_org_id),
):
    rows = await _load_rows(db, limit=1000)
    entities = _entity_records(rows)
    entity_types = Counter(item["entity_type"] for item in entities)
    relation_types = Counter(
        str(row.get("relationship") or "related_to") for row in rows
    )
    return api_success(
        data={
            "entity_types": [
                {"type": name, "count": count}
                for name, count in entity_types.most_common()
            ],
            "relation_types": [
                {"type": name, "count": count}
                for name, count in relation_types.most_common()
            ],
            "top_entities": [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "type": item["entity_type"],
                    "relation_count": item["relation_count"],
                }
                for item in entities[:10]
            ],
            "total_entities": len(entities),
            "total_relations": len(rows),
        }
    )
