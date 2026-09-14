from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.conversation_memory import storage
from app.services.conversation_memory.lineage import (
    filter_valid_consolidations,
    source_snapshot,
)
from app.services.knowledge_access_service import library_is_accessible


def query(data):
    q = MagicMock()
    for method in (
        "select",
        "eq",
        "is_",
        "in_",
        "order",
        "limit",
        "maybe_single",
        "delete",
        "update",
    ):
        getattr(q, method).return_value = q
    q.execute = AsyncMock(return_value=SimpleNamespace(data=data))
    return q


def source():
    return {
        "id": "s1",
        "user_id": "u",
        "organization_id": "a",
        "value": "validated parameter",
        "visibility": "private",
    }


def insight(row):
    return {
        "id": "c1",
        "user_id": "u",
        "organization_id": "a",
        "source_memory_ids": [row["id"]],
        "source_fingerprints": source_snapshot([row]),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        {"value": "changed"},
        {"visibility": "team"},
        {"organization_id": "b"},
        {"user_id": "v"},
        {"lifecycle_state": "archived"},
        {"superseded_by": "s2"},
        {"expires_at": "2000-01-01"},
        {"evidence_ref": "different-source"},
        {"metadata": {"document_id": "changed"}},
    ],
)
async def test_source_changes_invalidate_derived_insight(change):
    original = source()
    q = query([{**original, **change}])
    db = MagicMock()
    db.table.return_value = q
    assert (
        await filter_valid_consolidations(
            [insight(original)], user_id="u", org_id="a", db=db
        )
        == []
    )
    q.eq.assert_any_call("organization_id", "a")
    q.eq.assert_any_call("user_id", "u")


@pytest.mark.asyncio
async def test_missing_sources_legacy_and_malformed_snapshots_never_publish():
    original = source()
    good = insight(original)
    db = MagicMock()
    db.table.return_value = query([])
    assert (
        await filter_valid_consolidations([good], user_id="u", org_id="a", db=db) == []
    )
    db.table.return_value = query([original])
    assert await filter_valid_consolidations(
        [good], user_id="u", org_id="a", db=db
    ) == [good]
    for change in [
        {"source_fingerprints": {}},
        {"source_fingerprints": {"s1": None}},
        {"invalidated_at": "2026-09-14"},
        {"source_memory_ids": ["s1", "s2"]},
        {"organization_id": "b"},
    ]:
        assert (
            await filter_valid_consolidations(
                [{**good, **change}], user_id="u", org_id="a", db=db
            )
            == []
        )


@pytest.mark.asyncio
async def test_usage_counters_do_not_invalidate_sources():
    row = source()
    saved = insight(row)
    db = MagicMock()
    db.table.return_value = query(
        [{**row, "access_count": 30, "importance": 0.8, "is_consolidated": True}]
    )
    assert await filter_valid_consolidations(
        [saved], user_id="u", org_id="a", db=db
    ) == [saved]


@pytest.mark.asyncio
async def test_delete_and_clear_bind_active_enterprise_even_for_service_role():
    q = query([{"id": "s1"}])
    q.maybe_single.return_value = query({"key": "same-key", "organization_id": "a"})
    db = MagicMock()
    db.table.return_value = q
    await storage.delete_memory("u", "s1", db=db, org_id="a")
    q.eq.assert_any_call("organization_id", "a")
    q.eq.assert_any_call("key", "same-key")
    q.eq.reset_mock()
    await storage.clear_memories("u", db=db, org_id="b")
    q.eq.assert_any_call("organization_id", "b")


def test_library_catalog_private_department_and_templates():
    base = {"tenant_id": "a", "access_level": "organization"}

    def allowed(row):
        return library_is_accessible(
            row, organization_id="a", user_id="u", department_ids={"d1"}
        )

    assert allowed(base)
    assert not allowed({**base, "tenant_id": "b"})
    assert allowed({**base, "access_level": "private", "owner_id": "u"})
    assert not allowed({**base, "access_level": "private", "owner_id": "v"})
    assert allowed({**base, "access_level": "department", "department_id": "d1"})
    assert not allowed({**base, "access_level": "department", "department_id": "d2"})
    assert allowed({"tenant_id": None, "library_code": "product_lib"})
    assert not allowed({"tenant_id": None, "library_code": "custom-secret"})
    assert not allowed(
        {"tenant_id": None, "library_code": "product_lib", "owner_id": "v"}
    )


@pytest.mark.asyncio
async def test_catalog_route_filters_privileged_results_and_zeros_global_counts(
    monkeypatch,
):
    from app.core import database
    from app.routers.documents import list_knowledge_libraries

    rows = [
        {"id": 1, "tenant_id": "a", "access_level": "organization"},
        {"id": 2, "tenant_id": "b"},
        {"id": 3, "tenant_id": None, "library_code": "product_lib", "doc_count": 99},
    ]
    tenant = query(rows[:2])
    templates = query(rows[2:])
    db = MagicMock()
    db.table.side_effect = [tenant, templates]
    monkeypatch.setattr(database, "supabase", db)
    req = SimpleNamespace(state=SimpleNamespace(org_id="a"))
    result = await list_knowledge_libraries(req, _user_id="u")
    assert [row["id"] for row in result["data"]] == [1, 3]
    assert result["data"][1]["doc_count"] == 0
    tenant.eq.assert_any_call("tenant_id", "a")
    templates.is_.assert_any_call("tenant_id", "null")
