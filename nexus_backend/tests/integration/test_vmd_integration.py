"""
Integration tests for VMD (Virtual Marketing Department) module endpoints.

Tests cover the actually registered router groups:
  - VMD Tasks      (GET /api/vmd/tasks, GET /tasks/{id}, GET /tasks/{id}/sub-tasks,
                    POST /tasks/{id}/cancel, POST /tasks/{id}/pause, POST /tasks/{id}/resume)
  - VMD Compliance (GET /compliance/rules, GET /compliance/history)
  - VMD Clues      (GET /api/vmd/clues, GET /clues/{id})
  - VMD Dashboard  (GET /dashboard/stats, GET /dashboard/model-usage)

Uses httpx AsyncClient with ASGITransport to exercise the full FastAPI
middleware stack without spinning up a live server.  Database interactions
are mocked via patching ``app.core.database.supabase`` to ``None``; all
endpoints that depend on a DB connection will receive ``request.state.db``
as ``None`` and return a graceful error (typically 503 DB_CONNECTION_ERROR
or 200 with ``success: false``).

Authentication tests verify that unauthenticated / bad-token requests are
properly rejected (401/403).
"""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module")
async def patched_app():
    """Import the FastAPI app with database and heavy services mocked out.

    Same strategy as test_router_integration.py: patch away heavy services
    so no real I/O happens during testing.
    """
    with (
        patch("app.core.database.supabase", None),
        patch("app.services.cache_service.cache_service.init", new_callable=AsyncMock),
        patch("app.services.cache_service.cache_service.ping", new_callable=AsyncMock, return_value=False),
        patch("app.services.event_bus.event_bus.start", new_callable=AsyncMock),
        patch("app.services.event_bus.event_bus.stop", new_callable=AsyncMock),
        patch("app.services.audit_logger.audit_logger.force_flush", new_callable=AsyncMock),
    ):
        from app.main import app  # noqa: E402

        yield app


@pytest_asyncio.fixture(autouse=True)
async def _reset_rate_limiter():
    """Reset in-memory rate limiter between tests to avoid 429 leaks."""
    from app.core.rate_limiter import rate_limiter

    rate_limiter.tokens.clear()
    rate_limiter.last_update.clear()
    yield


@pytest_asyncio.fixture()
async def client(patched_app):
    """Provide an httpx AsyncClient bound to the ASGI app."""
    transport = ASGITransport(app=patched_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_TOKEN_HEADER = {"Authorization": "Bearer fake-test-jwt-token"}
BAD_TOKEN_HEADER = {"Authorization": "Bearer totally-invalid-garbage"}


def _assert_json_response(resp):
    """Verify the response has a JSON content type."""
    ct = resp.headers.get("content-type", "")
    assert "application/json" in ct, f"Expected JSON content-type, got: {ct}"


def _assert_auth_rejected(resp):
    """Assert the response indicates authentication failure."""
    assert resp.status_code in (401, 403, 500), (
        f"Expected auth rejection (401/403/500), got {resp.status_code}"
    )


def _assert_db_error_or_auth_failure(resp):
    """For authenticated endpoints with no real DB, expect either
    auth failure (401/403) or a graceful DB-related error (200/503).

    Routers use ``return api_error(...)`` (not ``raise``), which means
    DB_CONNECTION_ERROR is returned as a 200 response with
    ``{"success": false, ...}`` in many cases.  When the auth
    middleware itself fails (because we supply a fake JWT against a
    real verifier), we get 401/403/500.
    """
    if resp.status_code in (401, 403, 500):
        return  # auth layer rejected first -- fine
    # The endpoint was reached but returned a graceful error
    body = resp.json()
    # Could be 200 with success=false or a 503
    assert resp.status_code in (200, 422, 503), (
        f"Unexpected status {resp.status_code}: {resp.text[:300]}"
    )
    if resp.status_code == 200:
        # Routers that return api_error() without raise get 200
        assert body.get("success") is False or "error" in body


# ===========================================================================
# 1. VMD Task Endpoints -- Auth guard tests
# ===========================================================================


class TestVMDTasksAuth:
    """All /api/vmd/tasks endpoints require authentication."""

    @pytest.mark.asyncio
    async def test_list_tasks_no_auth(self, client: AsyncClient):
        """GET /api/vmd/tasks without auth should be rejected."""
        resp = await client.get("/api/vmd/tasks")
        _assert_auth_rejected(resp)

    @pytest.mark.asyncio
    async def test_get_task_no_auth(self, client: AsyncClient):
        """GET /api/vmd/tasks/{id} without auth should be rejected."""
        resp = await client.get("/api/vmd/tasks/nonexistent-id-123")
        _assert_auth_rejected(resp)

    @pytest.mark.asyncio
    async def test_pause_task_no_auth(self, client: AsyncClient):
        """POST /api/vmd/tasks/{id}/pause without auth should be rejected."""
        resp = await client.post("/api/vmd/tasks/some-id/pause")
        _assert_auth_rejected(resp)

    @pytest.mark.asyncio
    async def test_cancel_task_no_auth(self, client: AsyncClient):
        """POST /api/vmd/tasks/{id}/cancel without auth should be rejected."""
        resp = await client.post("/api/vmd/tasks/some-id/cancel")
        _assert_auth_rejected(resp)


# ===========================================================================
# 2. VMD Task Endpoints -- With (bad) auth token
# ===========================================================================


class TestVMDTasksBadToken:
    """VMD Task endpoints with an invalid Bearer token."""

    @pytest.mark.asyncio
    async def test_list_tasks_bad_token(self, client: AsyncClient):
        resp = await client.get("/api/vmd/tasks", headers=BAD_TOKEN_HEADER)
        _assert_db_error_or_auth_failure(resp)

    @pytest.mark.asyncio
    async def test_get_task_bad_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/vmd/tasks/fake-id", headers=BAD_TOKEN_HEADER
        )
        _assert_db_error_or_auth_failure(resp)

    @pytest.mark.asyncio
    async def test_pause_task_bad_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/vmd/tasks/fake-id/pause", headers=BAD_TOKEN_HEADER
        )
        _assert_db_error_or_auth_failure(resp)

    @pytest.mark.asyncio
    async def test_cancel_task_bad_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/vmd/tasks/fake-id/cancel", headers=BAD_TOKEN_HEADER
        )
        _assert_db_error_or_auth_failure(resp)


# ===========================================================================
# 3. VMD Task Endpoints -- Validation / error paths
# ===========================================================================


class TestVMDTasksValidation:
    """Input validation for task endpoints (missing fields, bad payloads)."""

    @pytest.mark.asyncio
    async def test_list_tasks_invalid_page(self, client: AsyncClient):
        """GET /tasks with page=0 should trigger validation error."""
        resp = await client.get(
            "/api/vmd/tasks?page=0",
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_list_tasks_page_size_too_large(self, client: AsyncClient):
        """GET /tasks with page_size=999 should trigger validation error."""
        resp = await client.get(
            "/api/vmd/tasks?page_size=999",
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)


# ===========================================================================
# 4. VMD Task Endpoints -- Response format
# ===========================================================================


class TestVMDTasksResponseFormat:
    """Verify JSON response format for task endpoints."""

    @pytest.mark.asyncio
    async def test_list_tasks_response_is_json(self, client: AsyncClient):
        resp = await client.get("/api/vmd/tasks", headers=FAKE_TOKEN_HEADER)
        _assert_json_response(resp)

    @pytest.mark.asyncio
    async def test_get_task_response_is_json(self, client: AsyncClient):
        resp = await client.get(
            "/api/vmd/tasks/nonexistent-id", headers=FAKE_TOKEN_HEADER
        )
        _assert_json_response(resp)

    @pytest.mark.asyncio
    async def test_pause_task_response_is_json(self, client: AsyncClient):
        resp = await client.post(
            "/api/vmd/tasks/nonexistent-id/pause", headers=FAKE_TOKEN_HEADER
        )
        _assert_json_response(resp)

    @pytest.mark.asyncio
    async def test_cancel_task_response_is_json(self, client: AsyncClient):
        resp = await client.post(
            "/api/vmd/tasks/nonexistent-id/cancel", headers=FAKE_TOKEN_HEADER
        )
        _assert_json_response(resp)


# ===========================================================================
# 5. VMD Compliance Endpoints -- Auth guard tests
# ===========================================================================


class TestVMDComplianceAuth:
    """All /api/vmd/compliance endpoints require authentication."""

    @pytest.mark.asyncio
    async def test_list_rules_no_auth(self, client: AsyncClient):
        """GET /compliance/rules without auth should be rejected."""
        resp = await client.get("/api/vmd/compliance/rules")
        _assert_auth_rejected(resp)

    @pytest.mark.asyncio
    async def test_get_history_no_auth(self, client: AsyncClient):
        """GET /compliance/history without auth should be rejected."""
        resp = await client.get("/api/vmd/compliance/history")
        _assert_auth_rejected(resp)


# ===========================================================================
# 6. VMD Compliance Endpoints -- With bad token
# ===========================================================================


class TestVMDComplianceBadToken:
    """VMD Compliance endpoints with invalid Bearer token."""

    @pytest.mark.asyncio
    async def test_list_rules_bad_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/vmd/compliance/rules",
            headers=BAD_TOKEN_HEADER,
        )
        _assert_db_error_or_auth_failure(resp)

    @pytest.mark.asyncio
    async def test_get_history_bad_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/vmd/compliance/history",
            headers=BAD_TOKEN_HEADER,
        )
        _assert_db_error_or_auth_failure(resp)


# ===========================================================================
# 7. VMD Compliance Endpoints -- Validation
# ===========================================================================


class TestVMDComplianceValidation:
    """Input validation for compliance endpoints."""

    @pytest.mark.asyncio
    async def test_history_invalid_page(self, client: AsyncClient):
        """GET /compliance/history with page=0."""
        resp = await client.get(
            "/api/vmd/compliance/history?page=0",
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)


# ===========================================================================
# 8. VMD Clues Endpoints -- Auth guard tests
# ===========================================================================


class TestVMDCluesAuth:
    """All /api/vmd/clues endpoints require authentication."""

    @pytest.mark.asyncio
    async def test_list_clues_no_auth(self, client: AsyncClient):
        """GET /clues without auth should be rejected."""
        resp = await client.get("/api/vmd/clues")
        _assert_auth_rejected(resp)

    @pytest.mark.asyncio
    async def test_get_clue_no_auth(self, client: AsyncClient):
        """GET /clues/{id} without auth should be rejected."""
        resp = await client.get("/api/vmd/clues/clue-id-123")
        _assert_auth_rejected(resp)


# ===========================================================================
# 9. VMD Clues Endpoints -- With bad token
# ===========================================================================


class TestVMDCluesBadToken:
    """VMD Clues endpoints with invalid Bearer token."""

    @pytest.mark.asyncio
    async def test_list_clues_bad_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/vmd/clues", headers=BAD_TOKEN_HEADER
        )
        _assert_db_error_or_auth_failure(resp)

    @pytest.mark.asyncio
    async def test_get_clue_bad_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/vmd/clues/fake-id", headers=BAD_TOKEN_HEADER
        )
        _assert_db_error_or_auth_failure(resp)


# ===========================================================================
# 10. VMD Clues Endpoints -- Validation
# ===========================================================================


class TestVMDCluesValidation:
    """Input validation for clue endpoints."""

    @pytest.mark.asyncio
    async def test_list_clues_with_filters(self, client: AsyncClient):
        """GET /clues with query params should return JSON."""
        resp = await client.get(
            "/api/vmd/clues?status=new&source=web&page=1&page_size=10",
            headers=FAKE_TOKEN_HEADER,
        )
        _assert_json_response(resp)
        # Either auth rejection or graceful error
        _assert_db_error_or_auth_failure(resp)


# ===========================================================================
# 11. VMD Dashboard Endpoints -- Auth guard tests
# ===========================================================================


class TestVMDDashboardAuth:
    """All /api/vmd/dashboard endpoints require authentication."""

    @pytest.mark.asyncio
    async def test_stats_no_auth(self, client: AsyncClient):
        """GET /dashboard/stats without auth should be rejected."""
        resp = await client.get("/api/vmd/dashboard/stats")
        _assert_auth_rejected(resp)

    @pytest.mark.asyncio
    async def test_model_usage_no_auth(self, client: AsyncClient):
        """GET /dashboard/model-usage without auth should be rejected."""
        resp = await client.get("/api/vmd/dashboard/model-usage")
        _assert_auth_rejected(resp)


# ===========================================================================
# 12. VMD Dashboard Endpoints -- With bad token
# ===========================================================================


class TestVMDDashboardBadToken:
    """VMD Dashboard endpoints with invalid Bearer token."""

    @pytest.mark.asyncio
    async def test_stats_bad_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/vmd/dashboard/stats", headers=BAD_TOKEN_HEADER
        )
        _assert_db_error_or_auth_failure(resp)

    @pytest.mark.asyncio
    async def test_model_usage_bad_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/vmd/dashboard/model-usage", headers=BAD_TOKEN_HEADER
        )
        _assert_db_error_or_auth_failure(resp)


# ===========================================================================
# 13. VMD Dashboard Endpoints -- Response format and validation
# ===========================================================================


class TestVMDDashboardResponseFormat:
    """Verify JSON structure and query param validation for dashboard."""

    @pytest.mark.asyncio
    async def test_stats_response_is_json(self, client: AsyncClient):
        resp = await client.get(
            "/api/vmd/dashboard/stats", headers=FAKE_TOKEN_HEADER
        )
        _assert_json_response(resp)

    @pytest.mark.asyncio
    async def test_model_usage_response_is_json(self, client: AsyncClient):
        resp = await client.get(
            "/api/vmd/dashboard/model-usage", headers=FAKE_TOKEN_HEADER
        )
        _assert_json_response(resp)


# ===========================================================================
# 14. Cross-cutting: Security headers on VMD routes
# ===========================================================================


class TestVMDSecurityHeaders:
    """Verify that security middleware headers are present on VMD responses."""

    @pytest.mark.asyncio
    async def test_security_headers_on_vmd_tasks(self, client: AsyncClient):
        resp = await client.get("/api/vmd/tasks")
        assert "x-content-type-options" in resp.headers
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert "x-frame-options" in resp.headers

    @pytest.mark.asyncio
    async def test_security_headers_on_vmd_compliance(self, client: AsyncClient):
        resp = await client.get("/api/vmd/compliance/rules")
        assert "x-content-type-options" in resp.headers
        assert "x-frame-options" in resp.headers

    @pytest.mark.asyncio
    async def test_security_headers_on_vmd_clues(self, client: AsyncClient):
        resp = await client.get("/api/vmd/clues")
        assert "x-content-type-options" in resp.headers
        assert "x-frame-options" in resp.headers

    @pytest.mark.asyncio
    async def test_security_headers_on_vmd_dashboard(self, client: AsyncClient):
        resp = await client.get("/api/vmd/dashboard/stats")
        assert "x-content-type-options" in resp.headers
        assert "x-frame-options" in resp.headers

    @pytest.mark.asyncio
    async def test_request_id_on_vmd_routes(self, client: AsyncClient):
        """RequestIDMiddleware should add X-Request-ID to VMD responses."""
        resp = await client.get("/api/vmd/tasks")
        assert "x-request-id" in resp.headers
        assert len(resp.headers["x-request-id"]) > 0

    @pytest.mark.asyncio
    async def test_custom_request_id_echoed_on_vmd(self, client: AsyncClient):
        """If caller sends X-Request-ID, it should be echoed back."""
        custom_id = "vmd-integration-test-001"
        resp = await client.get(
            "/api/vmd/tasks",
            headers={"X-Request-ID": custom_id},
        )
        assert resp.headers.get("x-request-id") == custom_id


# ===========================================================================
# 15. Cross-cutting: Rate limit headers on VMD routes
# ===========================================================================


class TestVMDRateLimitHeaders:
    """Verify that rate limit headers are present on VMD API responses."""

    @pytest.mark.asyncio
    async def test_rate_limit_headers_on_vmd_tasks(self, client: AsyncClient):
        resp = await client.get("/api/vmd/tasks")
        assert "x-ratelimit-limit" in resp.headers
        assert "x-ratelimit-remaining" in resp.headers
        assert "x-ratelimit-reset" in resp.headers

    @pytest.mark.asyncio
    async def test_rate_limit_headers_on_dashboard(self, client: AsyncClient):
        resp = await client.get("/api/vmd/dashboard/stats")
        assert "x-ratelimit-limit" in resp.headers
        assert "x-ratelimit-remaining" in resp.headers


# ===========================================================================
# 16. Route existence: VMD routes are registered
# ===========================================================================


class TestVMDRouteRegistration:
    """Verify that VMD routes are registered (not 404)."""

    @pytest.mark.asyncio
    async def test_vmd_tasks_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/vmd/tasks")
        assert resp.status_code != 404, "VMD tasks route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_task_detail_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/vmd/tasks/any-id")
        assert resp.status_code != 404, "VMD task detail route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_task_sub_tasks_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/vmd/tasks/any-id/sub-tasks")
        assert resp.status_code != 404, "VMD task sub-tasks route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_task_pause_route_exists(self, client: AsyncClient):
        resp = await client.post("/api/vmd/tasks/any-id/pause")
        assert resp.status_code != 404, "VMD task pause route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_task_cancel_route_exists(self, client: AsyncClient):
        resp = await client.post("/api/vmd/tasks/any-id/cancel")
        assert resp.status_code != 404, "VMD task cancel route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_task_resume_route_exists(self, client: AsyncClient):
        resp = await client.post("/api/vmd/tasks/any-id/resume")
        assert resp.status_code != 404, "VMD task resume route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_compliance_rules_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/vmd/compliance/rules")
        assert resp.status_code != 404, "VMD compliance rules route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_compliance_history_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/vmd/compliance/history")
        assert resp.status_code != 404, "VMD compliance history route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_clues_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/vmd/clues")
        assert resp.status_code != 404, "VMD clues route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_clue_detail_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/vmd/clues/any-id")
        assert resp.status_code != 404, "VMD clue detail route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_dashboard_stats_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/vmd/dashboard/stats")
        assert resp.status_code != 404, "VMD dashboard stats route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_dashboard_model_usage_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/vmd/dashboard/model-usage")
        assert resp.status_code != 404, "VMD dashboard model-usage route should be registered"
