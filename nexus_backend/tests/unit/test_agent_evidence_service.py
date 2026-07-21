from types import SimpleNamespace

import pytest

from app.agent.artifact_contract import ArtifactSpec, ArtifactType
from app.agent.scientific_writing_skills import enrich_artifact_spec
from app.services.agent_evidence_service import retrieve_agent_evidence
from app.services.vector_service import vector_service


@pytest.mark.asyncio
async def test_retrieval_is_tenant_scoped_section_aware_and_citable(monkeypatch):
    calls = []

    async def fake_search(query, user_id, limit=6, *, org_id, config=None):
        del limit, config
        calls.append((query, user_id, org_id))
        index = len(calls)
        return [
            {
                "document_id": f"doc-{index}",
                "chunk_id": f"chunk-{index}",
                "title": "企业资料",
                "excerpt": f"已核验证据 {index}",
                "score": 0.9,
                "source_version": "2026.1",
            }
        ]

    monkeypatch.setattr(vector_service, "search_evidence", fake_search)
    spec = enrich_artifact_spec(
        ArtifactSpec(
            artifact_type=ArtifactType.CUSTOMER_SOLUTION,
            strict_quality=True,
            external_delivery=True,
        )
    )
    config = SimpleNamespace(
        org_id="11111111-1111-4111-8111-111111111111",
        user_id="22222222-2222-4222-8222-222222222222",
        user_role="employee",
        rag_inject_limit=4,
    )

    packet = await retrieve_agent_evidence(
        query="液相色谱方案",
        config=config,
        artifact_spec=spec,
    )

    assert len(calls) == 6
    assert all(call[1:] == (config.user_id, config.org_id) for call in calls)
    assert packet.coverage == 1.0
    assert packet.sufficient is True
    assert len(packet.records) == 6
    assert "[EVID:doc-1:chunk-1]" in packet.prompt_context
    assert packet.fingerprint


@pytest.mark.asyncio
async def test_missing_topic_keeps_external_evidence_insufficient(monkeypatch):
    call_count = 0

    async def partial_search(query, user_id, limit=6, *, org_id, config=None):
        nonlocal call_count
        del query, user_id, limit, org_id, config
        call_count += 1
        if call_count == 1:
            return []
        return [
            {
                "document_id": f"doc-{call_count}",
                "chunk_id": f"chunk-{call_count}",
                "excerpt": "evidence",
            }
        ]

    monkeypatch.setattr(vector_service, "search_evidence", partial_search)
    spec = enrich_artifact_spec(
        ArtifactSpec(
            artifact_type=ArtifactType.TENDER,
            strict_quality=True,
            external_delivery=True,
        )
    )
    config = SimpleNamespace(
        org_id="11111111-1111-4111-8111-111111111111",
        user_id="22222222-2222-4222-8222-222222222222",
        user_role="employee",
        rag_inject_limit=4,
    )

    packet = await retrieve_agent_evidence(
        query="某科学仪器投标",
        config=config,
        artifact_spec=spec,
    )

    assert packet.coverage < spec.min_evidence_coverage
    assert packet.sufficient is False
    assert len(packet.missing_topics) == 1


@pytest.mark.asyncio
async def test_one_repeated_chunk_cannot_satisfy_all_external_topics(monkeypatch):
    async def repeated_search(query, user_id, limit=6, *, org_id, config=None):
        del query, user_id, limit, org_id, config
        return [
            {
                "document_id": "doc-1",
                "chunk_id": "chunk-1",
                "excerpt": "single broad statement",
            }
        ]

    monkeypatch.setattr(vector_service, "search_evidence", repeated_search)
    spec = enrich_artifact_spec(
        ArtifactSpec(
            artifact_type=ArtifactType.CUSTOMER_SOLUTION,
            strict_quality=True,
            external_delivery=True,
        )
    )
    config = SimpleNamespace(
        org_id="11111111-1111-4111-8111-111111111111",
        user_id="22222222-2222-4222-8222-222222222222",
        user_role="employee",
        rag_inject_limit=4,
    )

    packet = await retrieve_agent_evidence(
        query="液相色谱方案",
        config=config,
        artifact_spec=spec,
    )

    assert packet.coverage == 1.0
    assert len(packet.records) == 1
    assert packet.minimum_record_count == 3
    assert packet.sufficient is False
