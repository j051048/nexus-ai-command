"""Embedding plans for business entities and graph relationships."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.services.graph_rag_models import BusinessGraphDocument


@dataclass(frozen=True)
class EntityEmbeddingSpec:
    table: str
    entity_type: str
    id_field: str
    text_fields: tuple[str, ...]
    metadata_fields: tuple[str, ...] = ()


ENTITY_EMBEDDING_SPECS: tuple[EntityEmbeddingSpec, ...] = (
    EntityEmbeddingSpec(
        table="customers",
        entity_type="customer",
        id_field="id",
        text_fields=("name", "company", "stage", "industry"),
        metadata_fields=("assigned_to", "estimated_value", "updated_at"),
    ),
    EntityEmbeddingSpec(
        table="projects",
        entity_type="project",
        id_field="id",
        text_fields=("name", "customer_name", "stage", "status", "progress"),
        metadata_fields=("customer_id", "owner_id", "updated_at"),
    ),
    EntityEmbeddingSpec(
        table="contracts",
        entity_type="contract",
        id_field="id",
        text_fields=("title", "status", "amount", "end_date"),
        metadata_fields=("customer_id", "project_id", "updated_at"),
    ),
    EntityEmbeddingSpec(
        table="approval_requests",
        entity_type="approval",
        id_field="id",
        text_fields=("type", "title", "description", "status", "amount"),
        metadata_fields=("submitted_by", "requester_id", "created_at"),
    ),
    EntityEmbeddingSpec(
        table="action_events",
        entity_type="action_event",
        id_field="id",
        text_fields=("action_id", "source", "event_type", "status"),
        metadata_fields=("source_id", "user_id", "created_at"),
    ),
)


RELATIONSHIP_EMBEDDING_FIELDS = (
    "source",
    "relationship",
    "target",
    "label",
    "strength",
    "evidence",
)


def get_entity_embedding_plan() -> dict[str, Any]:
    """Return the offline contract for business entity embeddings."""

    return {
        "embedding_scope": "business_entities_and_relationships",
        "default_embedding_model": "text-embedding-3-small",
        "tenant_field": "organization_id",
        "entity_specs": [asdict(spec) for spec in ENTITY_EMBEDDING_SPECS],
        "relationship_embedding_fields": RELATIONSHIP_EMBEDDING_FIELDS,
        "index_contract": {
            "idempotent_key": "org_id + entity_type + entity_id",
            "dimension": 1536,
            "supports_from_existing_graph": True,
            "supports_relationship_embeddings": True,
        },
    }


def build_entity_embedding_candidates(
    graph_document: BusinessGraphDocument,
) -> list[dict[str, Any]]:
    """Create embedding rows for business graph nodes."""

    rows: list[dict[str, Any]] = []
    for node in graph_document.nodes:
        rows.append(
            {
                "org_id": graph_document.org_id,
                "entity_id": node.id,
                "entity_type": node.type,
                "content": node.embedding_text(),
                "metadata": {
                    "label": node.label,
                    "status": node.status,
                    "value": node.value,
                    **node.metadata,
                },
                "evidence_paths": [item.to_dict() for item in node.evidence],
            }
        )
    return rows


def build_relationship_embedding_candidates(
    graph_document: BusinessGraphDocument,
) -> list[dict[str, Any]]:
    """Create embedding rows for graph relationships/action edges."""

    labels = graph_document.node_labels
    rows: list[dict[str, Any]] = []
    for relationship in graph_document.relationships:
        rows.append(
            {
                "org_id": graph_document.org_id,
                "entity_id": f"{relationship.source}->{relationship.target}",
                "entity_type": "relationship",
                "relationship_type": relationship.type,
                "content": relationship.embedding_text(labels),
                "metadata": {
                    "source": relationship.source,
                    "target": relationship.target,
                    "label": relationship.label,
                    "strength": relationship.strength,
                    **relationship.metadata,
                },
                "evidence_paths": [item.to_dict() for item in relationship.evidence],
            }
        )
    return rows
