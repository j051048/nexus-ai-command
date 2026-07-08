from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def test_graph_rag_p0_p2_foundation_contract():
    models = read("nexus_backend/app/services/graph_rag_models.py")
    retrieval = read("nexus_backend/app/services/graph_rag_retrieval_service.py")
    embeddings = read("nexus_backend/app/services/business_entity_embedding_service.py")
    safety = read("nexus_backend/app/services/generated_query_safety.py")
    checkpoint = read("nexus_backend/app/services/checkpoint_observability_service.py")

    for token in [
        "EvidencePath",
        "BusinessGraphDocument",
        "BusinessGraphRelationship",
        "from_business_context_graph",
    ]:
        assert token in models

    for token in [
        "query_entity_extraction",
        "graph_neighborhood_expansion",
        "vector_hybrid_search",
        "metadata_filter",
        "mmr_diversity",
        "reranker",
        "context_packet",
    ]:
        assert token in retrieval

    assert "supports_from_existing_graph" in embeddings
    assert "supports_relationship_embeddings" in embeddings
    assert "allow_dangerous_requests" in safety
    assert "missing_tenant_guard" in safety
    assert "pending_write_count" in checkpoint
    assert "supports_human_review_debugging" in checkpoint
