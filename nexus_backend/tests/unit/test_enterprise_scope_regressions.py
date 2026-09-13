"""Boundary regressions without a running server, database or model provider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.conversation_memory import retrieval
from app.services.event_bus import Event


def query(data):
    result = MagicMock()
    for method in (
        "select",
        "eq",
        "is_",
        "in_",
        "gte",
        "order",
        "limit",
        "maybe_single",
        "insert",
        "update",
    ):
        getattr(result, method).return_value = result
    result.execute = AsyncMock(return_value=SimpleNamespace(data=data))
    return result


@pytest.mark.asyncio
async def test_l1_never_reuses_same_users_other_tenant_or_expired_facts(monkeypatch):
    good = {
        "id": "1",
        "user_id": "u",
        "organization_id": "org-a",
        "value": "current fact",
    }
    q = query(
        [
            good,
            {**good, "organization_id": "org-b", "value": "foreign fact"},
            {**good, "expires_at": "2000-01-01", "value": "expired fact"},
        ]
    )
    db = MagicMock()
    db.table.return_value = q
    monkeypatch.setattr(
        "app.services.conversation_memory.storage.decrypt_memory_value",
        lambda value: value,
    )
    context = await retrieval.get_l1_critical_facts("u", db=db, org_id="org-a")
    assert "current fact" in context
    assert "foreign fact" not in context and "expired fact" not in context
    assert ("organization_id", "org-a") in [call.args for call in q.eq.call_args_list]


@pytest.mark.asyncio
async def test_l2_forwards_scope_to_both_retrievers(monkeypatch):
    search = AsyncMock(return_value=[])
    consolidated = AsyncMock(return_value=[])
    monkeypatch.setattr(retrieval, "search_memories", search)
    monkeypatch.setattr(retrieval, "search_consolidations", consolidated)
    await retrieval.get_l2_contextual(
        "u", "customer context", org_id="org-a", user_role="manager"
    )
    assert search.await_args.kwargs["org_id"] == "org-a"
    assert search.await_args.kwargs["user_role"] == "manager"
    assert consolidated.await_args.kwargs["org_id"] == "org-a"


@pytest.mark.asyncio
async def test_context_builder_scopes_observation_and_all_lookups(monkeypatch):
    db = MagicMock()
    db.table.return_value = q = query([])
    mocks = {}
    for name in ("get_memories", "search_memories", "search_consolidations"):
        mocks[name] = AsyncMock(return_value=[])
        monkeypatch.setattr(retrieval, name, mocks[name])
    await retrieval.build_memory_context("u", "customer context", db=db, org_id="org-a")
    assert ("organization_id", "org-a") in [call.args for call in q.eq.call_args_list]
    for mock in mocks.values():
        assert mock.await_args.kwargs["org_id"] == "org-a"


@pytest.mark.asyncio
async def test_consolidations_revalidate_canonical_owner_and_tenant(monkeypatch):
    from app.services.vector_service import vector_service

    monkeypatch.setattr(vector_service, "embed_text", AsyncMock(return_value=[0.1]))
    db = MagicMock()
    db.rpc.return_value = query([{"id": "ok", "content": "stale"}, {"id": "foreign"}])
    db.table.return_value = query(
        [
            {
                "id": "ok",
                "user_id": "u",
                "organization_id": "org-a",
                "content": "current",
            },
            {"id": "foreign", "user_id": "u", "organization_id": "org-b"},
        ]
    )
    rows = await retrieval.search_consolidations("u", "context", db=db, org_id="org-a")
    assert [row["id"] for row in rows] == ["ok"]
    assert rows[0]["content"] == "current"
    assert db.rpc.call_args.args[1]["match_org_id"] == "org-a"


def guarded_handler(callback):
    async def handler(event):
        await callback(event)

    handler.__module__ = "app.services.event_bus"
    handler.__name__ = "auto_create_contract_from_deal"
    return handler


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation", ["consolidate_user_memories", "generate_user_observation"]
)
async def test_derived_memory_never_sends_foreign_facts_to_model(
    monkeypatch, operation
):
    from app.services.conversation_memory import consolidation
    from app.services.ai_service import AIService

    rows = [
        {
            "id": str(index),
            "user_id": "u",
            "organization_id": "other",
            "value": "foreign",
        }
        for index in range(6)
    ]
    db = MagicMock()
    db.table.return_value = q = query(rows)
    model = AsyncMock()
    monkeypatch.setattr(AIService, "call_llm", model)
    await getattr(consolidation, operation)("u", org_id="org-a", db=db)
    model.assert_not_awaited()
    assert ("organization_id", "org-a") in [call.args for call in q.eq.call_args_list]


@pytest.mark.asyncio
@pytest.mark.parametrize("claimed", [False, True])
async def test_business_receipt_gates_side_effect_and_completion(monkeypatch, claimed):
    from app.core import database
    from app.services.business_event_receipts import dispatch_business_event

    db = MagicMock()
    actor, receipt = query({"id": "u", "status": "active"}), query([])
    db.table.side_effect = lambda name: actor if name == "users" else receipt
    db.rpc.return_value = query({"claimed": claimed, "status": "processing"})
    monkeypatch.setattr(database, "supabase", db)
    callback = AsyncMock()
    await dispatch_business_event(
        guarded_handler(callback),
        Event(type="deal", organization_id="org-a", user_id="u"),
    )
    assert callback.await_count == int(claimed)
    assert ("organization_id", "org-a") in [
        call.args for call in actor.eq.call_args_list
    ]
    if claimed:
        receipt.update.assert_called_once_with({"status": "completed"})
    else:
        receipt.update.assert_not_called()


@pytest.mark.asyncio
async def test_business_handler_failure_requires_reconciliation(monkeypatch):
    from app.core import database
    from app.services.business_event_receipts import dispatch_business_event

    db = MagicMock()
    receipt = query([])
    db.table.side_effect = lambda name: (
        query({"id": "u"}) if name == "users" else receipt
    )
    db.rpc.return_value = query({"claimed": True})
    monkeypatch.setattr(database, "supabase", db)
    handler = guarded_handler(AsyncMock(side_effect=RuntimeError("business failure")))
    with pytest.raises(RuntimeError, match="business failure"):
        await dispatch_business_event(
            handler, Event(type="deal", organization_id="org-a", user_id="u")
        )
    receipt.update.assert_called_once_with({"status": "needs_attention"})


@pytest.mark.asyncio
@pytest.mark.parametrize("actor", [None, {"id": "u", "status": "disabled"}])
async def test_revoked_actor_cannot_claim_receipt(monkeypatch, actor):
    from app.core import database
    from app.services.business_event_receipts import dispatch_business_event

    db = MagicMock()
    db.table.return_value = query(actor)
    monkeypatch.setattr(database, "supabase", db)
    callback = AsyncMock()
    with pytest.raises(PermissionError):
        await dispatch_business_event(
            guarded_handler(callback),
            Event(type="deal", organization_id="org-a", user_id="u"),
        )
    db.rpc.assert_not_called()
    callback.assert_not_awaited()


@pytest.mark.parametrize(
    "url",
    [
        "https://user:pass@public.example",
        "https://public.example/#secret",
        "https://127.0.0.1",
        "https://169.254.169.254",
        "http://public.example",
    ],
)
def test_connector_rejects_unsafe_addresses(monkeypatch, url):
    from app.services.solution_connector_service import _validate_url

    monkeypatch.setenv(
        "SOLUTION_CONNECTOR_ALLOWED_HOSTS", "public.example,127.0.0.1,169.254.169.254"
    )
    with pytest.raises(ValueError):
        _validate_url(url)


def test_connector_requires_allowlist_even_for_public_hostname(monkeypatch):
    from app.services.solution_connector_service import _validate_url

    monkeypatch.delenv("SOLUTION_CONNECTOR_ALLOWED_HOSTS", raising=False)
    with pytest.raises(ValueError):
        _validate_url("https://public.example")
    monkeypatch.setenv("SOLUTION_CONNECTOR_ALLOWED_HOSTS", "public.example")
    assert _validate_url("https://public.example") == "https://public.example"
