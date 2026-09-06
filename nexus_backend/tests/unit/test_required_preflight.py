from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.preflight_rules import run_preflight_checks


def client_with_rows(rows):
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    query.execute = AsyncMock(return_value=SimpleNamespace(data=rows))
    client = MagicMock()
    client.table.return_value = query
    return client, query


@pytest.mark.asyncio
async def test_preflight_filters_record_and_tenant_without_sql_interpolation():
    client, query = client_with_rows([{"id": "customer"}])
    value = "customer' OR true --"
    passed, _ = await run_preflight_checks(
        "update_customer", {"customer_id": value}, client, org_id="org-a"
    )
    assert passed
    query.eq.assert_any_call("organization_id", "org-a")
    query.eq.assert_any_call("id", value)
    client.rpc.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["missing_client", "missing_org", "missing_id", "denied", "outage"])
async def test_required_preflight_fails_closed(mode):
    client, query = client_with_rows([] if mode == "denied" else [{"id": "customer"}])
    if mode == "outage":
        query.execute.side_effect = TimeoutError("database unavailable")
    passed, message = await run_preflight_checks(
        "update_customer", {} if mode == "missing_id" else {"customer_id": "customer"},
        None if mode == "missing_client" else client,
        org_id=None if mode == "missing_org" else "org-a",
    )
    assert not passed
    assert message


@pytest.mark.asyncio
async def test_tools_without_record_checks_do_not_require_database():
    assert await run_preflight_checks("load_knowledge", {}) == (True, "")


def test_query_cache_is_actor_and_tenant_scoped():
    from app.agent.node_execute import _get_cached_result, _set_cached_result

    _set_cached_result("get_customers", {}, "private", "org-a", "user-a")
    assert _get_cached_result("get_customers", {}, "org-a", "user-a") == "private"
    assert _get_cached_result("get_customers", {}, "org-a", "user-b") is None
    assert _get_cached_result("get_customers", {}, "org-b", "user-a") is None
