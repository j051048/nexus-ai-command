import pytest

from app.services.vector_service import (
    VectorService,
    document_name_relevance,
    sanitize_search_query,
)


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


def test_document_name_relevance_handles_exact_and_partial_model_mentions():
    filename = "FD-F多功能食品安全检测仪升级换代整体方案-专业版.docx"

    assert document_name_relevance(filename, filename) == 1.0
    assert (
        document_name_relevance(
            "参考那个FD-F多功能食品安全检测仪作为素材写方案", filename
        )
        >= 0.72
    )
    assert document_name_relevance("帮我写一份方案", filename) < 0.46


def test_search_sanitizer_preserves_scientific_instrument_model_codes():
    sanitized = sanitize_search_query("查询 FD-F、GC-MS；DROP TABLE--")

    assert "FD-F" in sanitized
    assert "GC-MS" in sanitized
    assert ";" not in sanitized
    assert "--" not in sanitized


def test_document_visibility_preserves_private_and_department_boundaries():
    service = VectorService()
    base = {"status": "ready", "review_status": "verified"}

    assert service._document_is_visible(
        {**base, "visibility": "organization", "owner_id": "another-user"},
        user_id="current-user",
        user_department="sales",
    )
    assert not service._document_is_visible(
        {**base, "visibility": "private", "owner_id": "another-user"},
        user_id="current-user",
        user_department="sales",
    )
    assert not service._document_is_visible(
        {**base, "visibility": "department", "department": "finance"},
        user_id="current-user",
        user_department="sales",
    )


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, data):
        self.data = data

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def in_(self, *_args, **_kwargs):
        return self

    def maybe_single(self):
        return self

    async def execute(self):
        return _Response(self.data)


class _Supabase:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return _Query(self.tables.get(name, []))


@pytest.mark.asyncio
async def test_filename_search_loads_org_document_uploaded_by_another_user(
    monkeypatch,
):
    from app.services import vector_service as vector_module

    org_id = "11111111-1111-4111-8111-111111111111"
    document_id = "22222222-2222-4222-8222-222222222222"
    chunk_id = "33333333-3333-4333-8333-333333333333"
    filename = "FD-F多功能食品安全检测仪升级换代整体方案-专业版.docx"
    fake = _Supabase(
        {
            "documents": [
                {
                    "id": document_id,
                    "name": filename,
                    "status": "ready",
                    "organization_id": org_id,
                    "owner_id": "44444444-4444-4444-8444-444444444444",
                    "visibility": "organization",
                    "review_status": "verified",
                    "doc_type": "proposal",
                }
            ],
            "users": {"department": "sales"},
            "document_embeddings": [
                {
                    "id": chunk_id,
                    "document_id": document_id,
                    "content": "FD-F 检测仪核心参数与泸州市项目实施方案。",
                    "metadata": {"source": filename},
                    "organization_id": org_id,
                    "chunk_type": "parent",
                    "access_groups": [],
                }
            ],
        }
    )
    monkeypatch.setattr(vector_module, "supabase", fake)

    rows, _ = await VectorService()._search_document_name_chunks(
        query="参考那个FD-F多功能食品安全检测仪作为素材写方案",
        user_id="55555555-5555-4555-8555-555555555555",
        org_id=org_id,
        limit=6,
    )

    assert len(rows) == 1
    assert rows[0]["document_id"] == document_id
    assert rows[0]["doc_metadata"]["name"] == filename
    assert rows[0]["match_kind"] == "document_name"


def test_legacy_rpc_rows_are_hydrated_with_canonical_document_id():
    document_id = "22222222-2222-4222-8222-222222222222"
    filename = "FD-F多功能食品安全检测仪升级换代整体方案-专业版.docx"

    rows = VectorService._hydrate_document_identity(
        [
            {
                "id": "33333333-3333-4333-8333-333333333333",
                "content": "正文",
                "metadata": {"source": filename},
                "similarity": 0.8,
            }
        ],
        [{"id": document_id, "name": filename, "doc_type": "proposal"}],
    )

    assert rows[0]["document_id"] == document_id
    assert rows[0]["doc_metadata"]["title"] == filename
