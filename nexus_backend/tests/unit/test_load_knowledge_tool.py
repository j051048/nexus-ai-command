from unittest.mock import AsyncMock

import pytest

from app.tools.load_knowledge_tool import LoadKnowledgeTool, _loaded_cache

ORG_ID = "11111111-1111-4111-8111-111111111111"
USER_ID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture(autouse=True)
def clear_loaded_knowledge_cache():
    _loaded_cache.clear()
    yield
    _loaded_cache.clear()


@pytest.mark.asyncio
async def test_empty_retrieval_is_not_cached(monkeypatch):
    from app.services.vector_service import vector_service

    search = AsyncMock(side_effect=[[], []])
    monkeypatch.setattr(vector_service, "search_evidence", search)
    tool = LoadKnowledgeTool()
    context = {
        "user_id": USER_ID,
        "org_id": ORG_ID,
        "session_id": "session-a",
    }

    first = await tool.execute({"query": "FD-F 产品方案"}, context)
    second = await tool.execute({"query": "FD-F 产品方案"}, context)

    assert "未找到" in first
    assert "未找到" in second
    assert search.await_count == 2


@pytest.mark.asyncio
async def test_successful_retrieval_replays_real_evidence(monkeypatch):
    from app.services.vector_service import vector_service

    search = AsyncMock(
        return_value=[
            {
                "document_id": "33333333-3333-4333-8333-333333333333",
                "chunk_id": "44444444-4444-4444-8444-444444444444",
                "title": "FD-F多功能食品安全检测仪方案.docx",
                "excerpt": "仪器参数、应用场景与实施计划。",
            }
        ]
    )
    monkeypatch.setattr(vector_service, "search_evidence", search)
    tool = LoadKnowledgeTool()
    context = {
        "user_id": USER_ID,
        "org_id": ORG_ID,
        "session_id": "session-b",
    }

    first = await tool.execute({"query": "FD-F 产品方案"}, context)
    second = await tool.execute({"query": "FD-F 产品方案"}, context)

    assert first == second
    assert "FD-F多功能食品安全检测仪方案.docx" in second
    assert "EVID:33333333-3333-4333-8333-333333333333" in second
    assert search.await_count == 1
