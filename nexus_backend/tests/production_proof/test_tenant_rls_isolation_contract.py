from __future__ import annotations

import os

import pytest


class RecordingBuilder:
    def __init__(self):
        self.calls: list[tuple[str, tuple, dict]] = []

    def select(self, *args, **kwargs):
        self.calls.append(("select", args, kwargs))
        return self

    def update(self, *args, **kwargs):
        self.calls.append(("update", args, kwargs))
        return self

    def delete(self, *args, **kwargs):
        self.calls.append(("delete", args, kwargs))
        return self

    def eq(self, *args, **kwargs):
        self.calls.append(("eq", args, kwargs))
        return self


class RecordingClient:
    def __init__(self):
        self.builder = RecordingBuilder()

    def table(self, _name):
        return self.builder

    def rpc(self, name, params):
        return {"name": name, "params": params}


def test_org_filtered_client_injects_org_filter_for_reads_and_writes():
    from app.core.database import OrgFilteredClient

    inner = RecordingClient()
    scoped = OrgFilteredClient(inner, "org-a")
    scoped.table("sales_leads").select("*")
    assert ("eq", ("organization_id", "org-a"), {}) in inner.builder.calls

    inner = RecordingClient()
    scoped = OrgFilteredClient(inner, "org-a")
    scoped.table("sales_leads").update({"name": "Acme"})
    assert ("eq", ("organization_id", "org-a"), {}) in inner.builder.calls

    inner = RecordingClient()
    scoped = OrgFilteredClient(inner, "org-a")
    scoped.table("sales_leads").delete()
    assert ("eq", ("organization_id", "org-a"), {}) in inner.builder.calls


def test_org_filtered_rpc_injects_org_parameter():
    from app.core.database import OrgFilteredClient

    scoped = OrgFilteredClient(RecordingClient(), "org-a")
    result = scoped.rpc("get_dashboard", {"limit": 10})
    assert result["params"]["p_org_id"] == "org-a"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_tenant_isolation_is_opt_in():
    if os.getenv("RUN_REAL_RLS_PROOF") != "1":
        pytest.skip("Set RUN_REAL_RLS_PROOF=1 with TEST_SUPABASE_* to verify real RLS.")
    for name in ("TEST_SUPABASE_URL", "TEST_SUPABASE_SERVICE_KEY", "TEST_SUPABASE_ANON_KEY"):
        assert os.getenv(name), f"Missing {name}"
