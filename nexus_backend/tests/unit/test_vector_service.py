import pytest

from app.services.vector_service import VectorService


@pytest.fixture
def vector_service():
    return VectorService()


def test_rrf_fusion_logic(vector_service):
    """
    Test Reciprocal Rank Fusion Logic explicitly.
    Case:
    - List A (Vector): [Doc 1, Doc 2]
    - List B (Keyword): [Doc 3, Doc 1]

    Scores (k=60):
    Doc 1: Rank 0 in A (1/61) + Rank 1 in B (1/62) ~= 0.01639 + 0.01612 = 0.0325
    Doc 2: Rank 1 in A (1/62) ~= 0.01612
    Doc 3: Rank 0 in B (1/61) ~= 0.01639

    Expected Order: Doc 1 > Doc 3 > Doc 2
    """
    list_a = [{"id": "doc1"}, {"id": "doc2"}]
    list_b = [{"id": "doc3"}, {"id": "doc1"}]

    fused = vector_service._rrf_fusion([list_a, list_b], k=60)

    # Sort by score desc
    sorted_docs = sorted(fused.values(), key=lambda x: x["score"], reverse=True)

    assert sorted_docs[0]["id"] == "doc1"  # Appeared in both
    assert sorted_docs[1]["id"] == "doc3"  # Rank 0 in list B
    assert sorted_docs[2]["id"] == "doc2"  # Rank 1 in list A


def test_rrf_empty(vector_service):
    assert vector_service._rrf_fusion([], k=60) == {}
    assert vector_service._rrf_fusion([[], []], k=60) == {}
