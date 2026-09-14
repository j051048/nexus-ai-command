from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ai_service import AIService
from app.services.conversation_memory import consolidation
from app.services.conversation_memory.lineage import source_snapshot
from app.services.vector_service import vector_service


def query(data):
    q = MagicMock()
    for method in (
        "select",
        "eq",
        "is_",
        "in_",
        "order",
        "limit",
        "insert",
        "update",
        "delete",
    ):
        getattr(q, method).return_value = q
    q.execute = AsyncMock(return_value=SimpleNamespace(data=data))
    return q


def setup_db(monkeypatch, count=6):
    rows = [
        {
            "id": str(i),
            "user_id": "u",
            "organization_id": "a",
            "category": "fact",
            "key": f"key-{i}",
            "value": f"source-{i}",
            "visibility": "private",
        }
        for i in range(count)
    ]
    source = query(rows)
    target = query([{"id": "new"}])
    db = MagicMock()
    db.table.side_effect = lambda name: (
        source if name == "conversation_memories" else target
    )
    monkeypatch.setattr(vector_service, "embed_text", AsyncMock(return_value=[0.1]))
    monkeypatch.setattr(consolidation, "decrypt_memory_value", lambda value: value)
    monkeypatch.setattr(
        AIService,
        "call_llm",
        AsyncMock(
            return_value='[{"title":"Insight","content":"Summary","source_indices":[0,1]}]'
        ),
    )
    return db, source, target, rows


@pytest.mark.asyncio
@pytest.mark.parametrize("empty", [False, True])
async def test_failed_insert_does_not_mark_sources_processed(monkeypatch, empty):
    db, source, target, _ = setup_db(monkeypatch)
    if empty:
        target.execute.return_value = SimpleNamespace(data=[])
    else:
        target.execute.side_effect = RuntimeError("storage unavailable")
    result = await consolidation.consolidate_user_memories("u", "a", db=db)
    assert result["insights_created"] == 0
    source.update.assert_not_called()


@pytest.mark.asyncio
async def test_all_model_inputs_are_tracked_but_only_persisted_citations_marked(
    monkeypatch,
):
    db, source, target, rows = setup_db(monkeypatch)
    result = await consolidation.consolidate_user_memories("u", "a", db=db)
    assert result["insights_created"] == 1
    saved = target.insert.call_args.args[0]
    assert saved["source_fingerprints"] == source_snapshot(rows)
    assert saved["source_memory_ids"] == [row["id"] for row in rows]
    source.in_.assert_called_once_with("id", ["0", "1"])
    source.eq.assert_any_call("organization_id", "a")


@pytest.mark.asyncio
async def test_observation_insert_failure_preserves_previous_profile(monkeypatch):
    db, _, target, _ = setup_db(monkeypatch, 30)
    AIService.call_llm.return_value = (
        "A complete observation of the user's preferences."
    )
    target.execute.side_effect = [
        SimpleNamespace(data=[{"id": "old"}]),
        RuntimeError("failed"),
    ]
    assert await consolidation.generate_user_observation("u", "a", db=db) is None
    target.delete.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("cleanup_failure", [False, True])
async def test_observation_keeps_new_result_and_cleans_only_snapshot_ids(
    monkeypatch, cleanup_failure
):
    db, _, target, rows = setup_db(monkeypatch, 30)
    AIService.call_llm.return_value = (
        "A complete observation of the user's preferences."
    )
    target.execute.side_effect = [
        SimpleNamespace(data=[{"id": "old"}]),
        SimpleNamespace(data=[{"id": "new"}]),
        (
            RuntimeError("cleanup unavailable")
            if cleanup_failure
            else SimpleNamespace(data=[])
        ),
    ]
    result = await consolidation.generate_user_observation("u", "a", db=db)
    assert result == {"id": "new"}
    saved = target.insert.call_args.args[0]
    assert saved["source_fingerprints"] == source_snapshot(rows)
    assert len(saved["source_memory_ids"]) == 30
    target.in_.assert_called_once_with("id", ["old"])
    target.eq.assert_any_call("user_id", "u")
    target.eq.assert_any_call("organization_id", "a")


@pytest.mark.asyncio
async def test_connections_refuse_cross_tenant_source_pairs():
    db = MagicMock()
    await consolidation._write_connections(
        [
            {"id": "s1", "user_id": "u", "organization_id": "a"},
            {"id": "s2", "user_id": "u", "organization_id": "b"},
        ],
        [{"from": 0, "to": 1}],
        db,
    )
    db.table.assert_not_called()
