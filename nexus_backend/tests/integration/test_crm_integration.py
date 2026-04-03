"""
CRM 路由集成测试
覆盖: 客户 CRUD、联系人、活动、统计、权限控制、静态端点
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import get_current_user_id
from app.main import app

CUSTOMER = {
    "id": "c-1",
    "organization_id": "org-1",
    "name": "测试客户",
    "company": "Test Corp",
    "industry": "tech",
    "stage": "prospect",
}

CONTACT = {"id": "ct-1", "customer_id": "c-1", "name": "张三", "phone": "13800000000"}
ACTIVITY = {"id": "a-1", "customer_id": "c-1", "activity_type": "call", "content": "电话沟通"}


def _patch_crm(method, return_value=None, side_effect=None):
    target = f"app.routers.crm.crm_service.{method}"
    if side_effect:
        return patch(target, new_callable=AsyncMock, side_effect=side_effect)
    return patch(target, new_callable=AsyncMock, return_value=return_value)


class _OrgInjectApp:
    """Wraps the FastAPI app to inject org_id/db into request.state
    AFTER the middleware stack runs, by monkey-patching scope state."""

    def __init__(self, app):
        self._app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            scope.setdefault("state", {})
            scope["state"]["org_id"] = "org-1"
            scope["state"]["db"] = MagicMock()
        await self._app(scope, receive, send)


@pytest.fixture
async def crm_client():
    """Client with auth overridden + TenantContextMiddleware bypassed."""

    async def _fake_user():
        return "user-1"

    app.dependency_overrides[get_current_user_id] = _fake_user

    # Bypass TenantContextMiddleware so it doesn't overwrite org_id/db
    with patch(
        "app.core.security_middleware.TenantContextMiddleware.dispatch",
        _passthrough_dispatch,
    ):
        wrapped = _OrgInjectApp(app)
        async with AsyncClient(transport=ASGITransport(app=wrapped), base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.pop(get_current_user_id, None)


async def _passthrough_dispatch(self, request, call_next):
    """Replacement dispatch that just injects org_id/db without auth."""
    request.state.org_id = "org-1"
    request.state.user_id = "user-1"
    request.state.db = MagicMock()
    request.state.auth_failed = False
    return await call_next(request)


# ---------------------------------------------------------------------------
# Customer CRUD
# ---------------------------------------------------------------------------


class TestListCustomers:
    @pytest.mark.asyncio
    async def test_list_customers(self, crm_client):
        with _patch_crm("list_customers", [CUSTOMER]):
            resp = await crm_client.get("/api/crm/customers")
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            assert len(body["data"]) == 1

    @pytest.mark.asyncio
    async def test_list_with_search(self, crm_client):
        with _patch_crm("search_customers", [CUSTOMER]):
            resp = await crm_client.get("/api/crm/customers?search=测试")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_with_filters(self, crm_client):
        with _patch_crm("list_customers", [CUSTOMER]):
            resp = await crm_client.get("/api/crm/customers?stage=prospect&industry=tech")
            assert resp.status_code == 200


class TestCreateCustomer:
    @pytest.mark.asyncio
    async def test_create_success(self, crm_client):
        with _patch_crm("create_customer", CUSTOMER):
            resp = await crm_client.post(
                "/api/crm/customers",
                json={"name": "新客户", "stage": "lead"},
            )
            assert resp.status_code == 200
            assert resp.json()["data"]["customer"]["name"] == "测试客户"

    @pytest.mark.asyncio
    async def test_create_invalid_stage_returns_422(self, crm_client):
        resp = await crm_client.post(
            "/api/crm/customers",
            json={"name": "X", "stage": "invalid_stage"},
        )
        assert resp.status_code == 422


class TestGetCustomer:
    @pytest.mark.asyncio
    async def test_get_success(self, crm_client):
        with _patch_crm("get_customer", CUSTOMER):
            resp = await crm_client.get("/api/crm/customers/c-1")
            assert resp.status_code == 200
            assert resp.json()["data"]["customer"]["id"] == "c-1"


class TestUpdateCustomer:
    @pytest.mark.asyncio
    async def test_update_success(self, crm_client):
        with _patch_crm("update_customer", {**CUSTOMER, "name": "更新"}):
            resp = await crm_client.put(
                "/api/crm/customers/c-1",
                json={"name": "更新"},
            )
            assert resp.status_code == 200


class TestDeleteCustomer:
    @pytest.mark.asyncio
    async def test_delete_success(self, crm_client):
        with _patch_crm("delete_customer", None), \
             patch("app.core.dependencies._get_user_role", new_callable=AsyncMock, return_value="boss"):
            resp = await crm_client.delete("/api/crm/customers/c-1")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


class TestContacts:
    @pytest.mark.asyncio
    async def test_list_contacts(self, crm_client):
        with _patch_crm("list_contacts", [CONTACT]):
            resp = await crm_client.get("/api/crm/customers/c-1/contacts")
            assert resp.status_code == 200
            assert len(resp.json()["data"]) == 1

    @pytest.mark.asyncio
    async def test_create_contact(self, crm_client):
        with _patch_crm("create_contact", CONTACT):
            resp = await crm_client.post(
                "/api/crm/customers/c-1/contacts",
                json={"name": "张三"},
            )
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_contact(self, crm_client):
        with _patch_crm("update_contact", {**CONTACT, "name": "李四"}):
            resp = await crm_client.put(
                "/api/crm/customers/c-1/contacts/ct-1",
                json={"name": "李四"},
            )
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_contact(self, crm_client):
        with _patch_crm("delete_contact", None):
            resp = await crm_client.delete("/api/crm/customers/c-1/contacts/ct-1")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Activities & Timeline
# ---------------------------------------------------------------------------


class TestActivities:
    @pytest.mark.asyncio
    async def test_create_activity(self, crm_client):
        with _patch_crm("create_activity", ACTIVITY):
            resp = await crm_client.post(
                "/api/crm/customers/c-1/activities",
                json={"activity_type": "call", "content": "电话沟通"},
            )
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_timeline(self, crm_client):
        with _patch_crm("get_activity_timeline", [ACTIVITY]):
            resp = await crm_client.get("/api/crm/customers/c-1/timeline")
            assert resp.status_code == 200
            assert len(resp.json()["data"]) == 1


# ---------------------------------------------------------------------------
# Stats & Static Endpoints
# ---------------------------------------------------------------------------


class TestStatsAndStatic:
    @pytest.mark.asyncio
    async def test_get_stats(self, crm_client):
        stats = {"total": 10, "by_stage": {"lead": 5, "prospect": 5}}
        with _patch_crm("get_customer_stats", stats):
            resp = await crm_client.get("/api/crm/stats")
            assert resp.status_code == 200
            assert resp.json()["data"]["stats"]["total"] == 10

    @pytest.mark.asyncio
    async def test_get_stages(self, crm_client):
        resp = await crm_client.get("/api/crm/stages")
        assert resp.status_code == 200
        assert "stages" in resp.json()["data"]

    @pytest.mark.asyncio
    async def test_get_activity_types(self, crm_client):
        resp = await crm_client.get("/api/crm/activity-types")
        assert resp.status_code == 200
        assert "activity_types" in resp.json()["data"]
