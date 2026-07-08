"""GraphRAG retrieval planning over the business context graph."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.business_context_graph import build_business_context_graph
from app.services.business_entity_embedding_service import (
    build_entity_embedding_candidates,
    build_relationship_embedding_candidates,
)
from app.services.graph_rag_models import BusinessGraphDocument, EvidencePath
from app.services.retrieval_security import (
    construct_metadata_filter,
    mmr_select_texts,
    require_org_scope,
)

GRAPH_RAG_RETRIEVAL_STEPS = (
    "query_entity_extraction",
    "graph_neighborhood_expansion",
    "vector_hybrid_search",
    "metadata_filter",
    "mmr_diversity",
    "reranker",
    "context_packet",
)


@dataclass(frozen=True)
class GraphRAGRetrievalPlan:
    query: str
    org_id: str
    user_id: str | None
    role: str | None
    steps: tuple[str, ...]
    metadata_filter: dict[str, Any]
    candidate_entities: list[str] = field(default_factory=list)
    expanded_entities: list[str] = field(default_factory=list)
    evidence_paths: list[EvidencePath] = field(default_factory=list)
    retrieval_modes: tuple[str, ...] = ("graph", "vector", "hybrid", "rerank")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence_paths"] = [item.to_dict() for item in self.evidence_paths]
        return data


@dataclass(frozen=True)
class GraphRAGContextPacket:
    plan: GraphRAGRetrievalPlan
    graph_document: BusinessGraphDocument
    entity_embeddings: list[dict[str, Any]]
    relationship_embeddings: list[dict[str, Any]]
    context_items: list[dict[str, Any]]
    prompt_context: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan.to_dict(),
            "graph_document": self.graph_document.to_dict(),
            "entity_embeddings": self.entity_embeddings,
            "relationship_embeddings": self.relationship_embeddings,
            "context_items": self.context_items,
            "prompt_context": self.prompt_context,
        }


def _query_terms(query: str) -> set[str]:
    return {term.lower() for term in re.findall(r"[\w\u4e00-\u9fff]{2,}", query or "")}


def _matches_query(text: str, terms: set[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _expand_neighborhood(
    graph_document: BusinessGraphDocument, seed_ids: set[str]
) -> set[str]:
    expanded = set(seed_ids)
    for edge in graph_document.relationships:
        if edge.source in seed_ids or edge.target in seed_ids:
            expanded.add(edge.source)
            expanded.add(edge.target)
    return expanded


def build_graph_rag_retrieval_plan(
    query: str,
    graph_document: BusinessGraphDocument,
    *,
    org_id: str,
    user_id: str | None = None,
    role: str | None = None,
    filters: dict[str, Any] | None = None,
) -> GraphRAGRetrievalPlan:
    """Build an observable retrieval plan before executing online search."""

    scoped_filters = require_org_scope(filters, org_id)
    construct_metadata_filter(scoped_filters)
    terms = _query_terms(query)

    seed_ids = {
        node.id
        for node in graph_document.nodes
        if _matches_query(node.label, terms)
        or _matches_query(node.embedding_text(), terms)
    }
    if not seed_ids:
        seed_ids = {node.id for node in graph_document.nodes[:5]}

    expanded_ids = _expand_neighborhood(graph_document, seed_ids)
    evidence = [
        EvidencePath(
            source="graph_rag_retrieval_plan",
            record_id=entity_id,
            confidence=0.9 if entity_id in seed_ids else 0.72,
            metadata={"matched_directly": entity_id in seed_ids},
        )
        for entity_id in sorted(expanded_ids)
    ]

    return GraphRAGRetrievalPlan(
        query=query,
        org_id=org_id,
        user_id=user_id,
        role=role,
        steps=GRAPH_RAG_RETRIEVAL_STEPS,
        metadata_filter=scoped_filters,
        candidate_entities=sorted(seed_ids),
        expanded_entities=sorted(expanded_ids),
        evidence_paths=evidence,
    )


def build_context_packet_from_graph(
    query: str,
    graph_document: BusinessGraphDocument,
    *,
    org_id: str,
    user_id: str | None = None,
    role: str | None = None,
    filters: dict[str, Any] | None = None,
    limit: int = 8,
) -> GraphRAGContextPacket:
    """Create a GraphRAG context packet from an already loaded graph."""

    plan = build_graph_rag_retrieval_plan(
        query,
        graph_document,
        org_id=org_id,
        user_id=user_id,
        role=role,
        filters=filters,
    )
    entity_rows = build_entity_embedding_candidates(graph_document)
    relationship_rows = build_relationship_embedding_candidates(graph_document)
    allowed_ids = set(plan.expanded_entities)
    ranked_input = [
        {
            "id": row["entity_id"],
            "text": row["content"],
            "score": 1.0 if row["entity_id"] in plan.candidate_entities else 0.72,
            "metadata": row["metadata"],
            "evidence_paths": row["evidence_paths"],
        }
        for row in [*entity_rows, *relationship_rows]
        if row["entity_id"] in allowed_ids
        or row.get("metadata", {}).get("source") in allowed_ids
        or row.get("metadata", {}).get("target") in allowed_ids
    ]
    context_items = mmr_select_texts(
        ranked_input, text_key="text", score_key="score", limit=limit
    )
    prompt_context = "\n".join(
        [graph_document.prompt_context]
        + [
            f"- {item['id']}: {item['text'][:280]}"
            for item in context_items
            if item.get("text")
        ]
    ).strip()
    return GraphRAGContextPacket(
        plan=plan,
        graph_document=graph_document,
        entity_embeddings=entity_rows,
        relationship_embeddings=relationship_rows,
        context_items=context_items,
        prompt_context=prompt_context,
    )


async def build_graph_rag_context_packet(
    db: Any,
    *,
    query: str,
    org_id: str,
    user_id: str | None = None,
    role: str | None = None,
    filters: dict[str, Any] | None = None,
    limit: int = 8,
) -> GraphRAGContextPacket:
    """Load the business graph and return a complete GraphRAG context packet."""

    graph = await build_business_context_graph(
        db,
        org_id=org_id,
        user_id=user_id,
        role=role,
    )
    graph_document = BusinessGraphDocument.from_business_context_graph(
        graph,
        org_id=org_id,
        source="business_context_graph",
    )
    return build_context_packet_from_graph(
        query,
        graph_document,
        org_id=org_id,
        user_id=user_id,
        role=role,
        filters=filters,
        limit=limit,
    )
