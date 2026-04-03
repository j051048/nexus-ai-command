"""
DSAR 路由集成测试
覆盖: 数据导出、导出状态查询、数据删除（需confirm）、删除状态查询、权限控制
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import get_current_user_id
from app.main import app


@pytest.fixture(autouse=True)
def clear_dsar_cache():
    """Clear the module-level DSAR request cache between tests."""
    from app.routers import dsar
    dsar._dsar_requests.clear()
    yield
    dsar._dsar_requests.clear()


@pytest.fixture
async def dsar_client():
    """Client with auth dependency overridden to return user-1."""

    async def _fake_user():
        return "user-1"

    app.dependency_overrides[get_current_user_id] = _fake_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_user_id, None)


class TestExport:
    """POST /api/dsar/export"""

    @pytest.mark.asyncio
    async def test_export_success(self, dsar_client):
        mock_svc = AsyncMock()
        mock_svc.export_user_data.return_value = {"status": "completed", "tables": {}}

        with patch("app.routers.dsar._get_dsar_service", return_value=mock_svc):
            resp = await dsar_client.post("/api/dsar/export", json={"reason": "GDPR"})
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            assert "request_id" in body["data"]

    @pytest.mark.asyncio
    async def test_export_service_failure_returns_500(self, dsar_client):
        mock_svc = AsyncMock()
        mock_svc.export_user_data.side_effect = Exception("DB down")

        with patch("app.routers.dsar._get_dsar_service", return_value=mock_svc):
            resp = await dsar_client.post("/api/dsar/export", json={})
            assert resp.status_code == 500


class TestExportStatus:
    """GET /api/dsar/export/{request_id}"""

    @pytest.mark.asyncio
    async def test_export_status_not_found(self, dsar_client):
        resp = await dsar_client.get("/api/dsar/export/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_export_status_wrong_user_returns_403(self, dsar_client):
        from app.routers import dsar
        dsar._dsar_requests["req-1"] = {
            "request_id": "req-1",
            "type": "export",
            "user_id": "other-user",
            "status": "completed",
            "created_at": "2026-01-01T00:00:00",
        }
        resp = await dsar_client.get("/api/dsar/export/req-1")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_export_status_success(self, dsar_client):
        from app.routers import dsar
        dsar._dsar_requests["req-1"] = {
            "request_id": "req-1",
            "type": "export",
            "user_id": "user-1",
            "status": "completed",
            "created_at": "2026-01-01T00:00:00",
            "result": {"tables": {}},
        }
        resp = await dsar_client.get("/api/dsar/export/req-1")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "completed"


class TestDelete:
    """POST /api/dsar/delete"""

    @pytest.mark.asyncio
    async def test_delete_without_confirm_returns_400(self, dsar_client):
        resp = await dsar_client.post(
            "/api/dsar/delete",
            json={"reason": "I want out", "confirm": False},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_success(self, dsar_client):
        mock_svc = AsyncMock()
        mock_svc.delete_user_data.return_value = {"status": "completed", "actions": {}}

        with patch("app.routers.dsar._get_dsar_service", return_value=mock_svc):
            resp = await dsar_client.post(
                "/api/dsar/delete",
                json={"reason": "GDPR right to be forgotten", "confirm": True},
            )
            assert resp.status_code == 200
            assert resp.json()["data"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_delete_service_failure_returns_500(self, dsar_client):
        mock_svc = AsyncMock()
        mock_svc.delete_user_data.side_effect = Exception("Permission denied")

        with patch("app.routers.dsar._get_dsar_service", return_value=mock_svc):
            resp = await dsar_client.post(
                "/api/dsar/delete",
                json={"reason": "test", "confirm": True},
            )
            assert resp.status_code == 500


class TestDeleteStatus:
    """GET /api/dsar/delete/{request_id}"""

    @pytest.mark.asyncio
    async def test_delete_status_not_found(self, dsar_client):
        resp = await dsar_client.get("/api/dsar/delete/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_status_wrong_user_returns_403(self, dsar_client):
        from app.routers import dsar
        dsar._dsar_requests["del-1"] = {
            "request_id": "del-1",
            "type": "delete",
            "user_id": "other-user",
            "status": "completed",
            "created_at": "2026-01-01T00:00:00",
        }
        resp = await dsar_client.get("/api/dsar/delete/del-1")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_status_success(self, dsar_client):
        from app.routers import dsar
        dsar._dsar_requests["del-1"] = {
            "request_id": "del-1",
            "type": "delete",
            "user_id": "user-1",
            "status": "completed",
            "created_at": "2026-01-01T00:00:00",
            "result": {"status": "completed", "actions": {"users": "anonymized"}, "errors": []},
        }
        resp = await dsar_client.get("/api/dsar/delete/del-1")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "completed"
        assert "tables_processed" in data["result"]
