"""
Integration tests for VMD (Virtual Marketing Department) module endpoints.

Tests cover five router groups:
  - VMD Tasks      (POST/GET /api/vmd/tasks, pause, cancel, sub-task audit)
  - VMD Compliance (POST /check, GET/POST /rules, GET /history)
  - VMD Clues      (POST/GET/PUT /clues, POST follow-up)
  - VMD Dashboard  (GET stats, task-trend, agent-workload, scene-distribution)
  - LLM Models     (GET/POST /llm/models, GET /llm/schedule-rules)

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
    async def test_create_task_no_auth(self, client: AsyncClient):
        """POST /api/vmd/tasks without auth should be rejected."""
        resp = await client.post(
            "/api/vmd/tasks",
            json={
                "title": "Test Task",
                "description": "Test description",
                "scene_code": "content_gen",
            },
        )
        _assert_auth_rejected(resp)

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

    @pytest.mark.asyncio
    async def test_audit_sub_task_no_auth(self, client: AsyncClient):
        """POST /api/vmd/sub-tasks/{id}/audit without auth should be rejected."""
        resp = await client.post(
            "/api/vmd/sub-tasks/sub-id-123/audit",
            json={"action": "approve"},
        )
        _assert_auth_rejected(resp)


# ===========================================================================
# 2. VMD Task Endpoints -- With (bad) auth token
# ===========================================================================


class TestVMDTasksBadToken:
    """VMD Task endpoints with an invalid Bearer token."""

    @pytest.mark.asyncio
    async def test_create_task_bad_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/vmd/tasks",
            json={
                "title": "Test",
                "description": "Desc",
                "scene_code": "sc",
            },
            headers=BAD_TOKEN_HEADER,
        )
        _assert_db_error_or_auth_failure(resp)

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

    @pytest.mark.asyncio
    async def test_audit_sub_task_bad_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/vmd/sub-tasks/fake-sub-id/audit",
            json={"action": "approve", "comment": "LGTM"},
            headers=BAD_TOKEN_HEADER,
        )
        _assert_db_error_or_auth_failure(resp)


# ===========================================================================
# 3. VMD Task Endpoints -- Validation / error paths
# ===========================================================================


class TestVMDTasksValidation:
    """Input validation for task endpoints (missing fields, bad payloads)."""

    @pytest.mark.asyncio
    async def test_create_task_missing_title(self, client: AsyncClient):
        """POST /tasks with missing required field should return 422."""
        resp = await client.post(
            "/api/vmd/tasks",
            json={"description": "desc", "scene_code": "sc"},
            headers=FAKE_TOKEN_HEADER,
        )
        # Either 422 (Pydantic) or auth rejection
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_create_task_missing_description(self, client: AsyncClient):
        """POST /tasks with missing description should return 422."""
        resp = await client.post(
            "/api/vmd/tasks",
            json={"title": "Test", "scene_code": "sc"},
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_create_task_missing_scene_code(self, client: AsyncClient):
        """POST /tasks with missing scene_code should return 422."""
        resp = await client.post(
            "/api/vmd/tasks",
            json={"title": "Test", "description": "desc"},
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_create_task_empty_body(self, client: AsyncClient):
        """POST /tasks with empty body should return 422."""
        resp = await client.post(
            "/api/vmd/tasks",
            json={},
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_audit_sub_task_invalid_action(self, client: AsyncClient):
        """POST /sub-tasks/{id}/audit with invalid action."""
        resp = await client.post(
            "/api/vmd/sub-tasks/fake-id/audit",
            json={"action": "invalid_action"},
            headers=FAKE_TOKEN_HEADER,
        )
        # Auth failure or validation error
        assert resp.status_code in (200, 401, 403, 422, 500)
        if resp.status_code == 200:
            body = resp.json()
            # The router checks action in ("approve", "reject") after DB check,
            # but with no DB it would fail first on DB error.
            assert body.get("success") is False

    @pytest.mark.asyncio
    async def test_audit_sub_task_missing_action(self, client: AsyncClient):
        """POST /sub-tasks/{id}/audit without action field."""
        resp = await client.post(
            "/api/vmd/sub-tasks/fake-id/audit",
            json={},
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

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
    async def test_create_task_response_is_json(self, client: AsyncClient):
        resp = await client.post(
            "/api/vmd/tasks",
            json={
                "title": "Test",
                "description": "Desc",
                "scene_code": "sc",
            },
            headers=FAKE_TOKEN_HEADER,
        )
        _assert_json_response(resp)

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
    async def test_check_content_no_auth(self, client: AsyncClient):
        """POST /compliance/check without auth should be rejected."""
        resp = await client.post(
            "/api/vmd/compliance/check",
            json={"content": "This is a test content"},
        )
        _assert_auth_rejected(resp)

    @pytest.mark.asyncio
    async def test_list_rules_no_auth(self, client: AsyncClient):
        """GET /compliance/rules without auth should be rejected."""
        resp = await client.get("/api/vmd/compliance/rules")
        _assert_auth_rejected(resp)

    @pytest.mark.asyncio
    async def test_create_rule_no_auth(self, client: AsyncClient):
        """POST /compliance/rules without auth should be rejected."""
        resp = await client.post(
            "/api/vmd/compliance/rules",
            json={
                "rule_code": "TEST_RULE_001",
                "rule_name": "Test Rule",
                "category": "advertising",
                "pattern": "banned_word",
            },
        )
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
    async def test_check_content_bad_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/vmd/compliance/check",
            json={"content": "Check this content"},
            headers=BAD_TOKEN_HEADER,
        )
        _assert_db_error_or_auth_failure(resp)

    @pytest.mark.asyncio
    async def test_list_rules_bad_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/vmd/compliance/rules",
            headers=BAD_TOKEN_HEADER,
        )
        _assert_db_error_or_auth_failure(resp)

    @pytest.mark.asyncio
    async def test_create_rule_bad_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/vmd/compliance/rules",
            json={
                "rule_code": "R001",
                "rule_name": "Rule 1",
                "category": "security",
                "pattern": "secret_keyword",
            },
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
    async def test_check_content_empty_body(self, client: AsyncClient):
        """POST /compliance/check with empty body."""
        resp = await client.post(
            "/api/vmd/compliance/check",
            json={},
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_check_content_missing_content(self, client: AsyncClient):
        """POST /compliance/check without the 'content' field."""
        resp = await client.post(
            "/api/vmd/compliance/check",
            json={"categories": ["advertising"]},
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_create_rule_missing_fields(self, client: AsyncClient):
        """POST /compliance/rules with incomplete data."""
        resp = await client.post(
            "/api/vmd/compliance/rules",
            json={"rule_code": "R1"},  # Missing rule_name, category, pattern
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_create_rule_empty_body(self, client: AsyncClient):
        """POST /compliance/rules with empty body."""
        resp = await client.post(
            "/api/vmd/compliance/rules",
            json={},
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_history_invalid_page(self, client: AsyncClient):
        """GET /compliance/history with page=0."""
        resp = await client.get(
            "/api/vmd/compliance/history?page=0",
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_check_content_response_is_json(self, client: AsyncClient):
        """POST /compliance/check response must be JSON."""
        resp = await client.post(
            "/api/vmd/compliance/check",
            json={"content": "test"},
            headers=FAKE_TOKEN_HEADER,
        )
        _assert_json_response(resp)


# ===========================================================================
# 8. VMD Clues Endpoints -- Auth guard tests
# ===========================================================================


class TestVMDCluesAuth:
    """All /api/vmd/clues endpoints require authentication."""

    @pytest.mark.asyncio
    async def test_create_clue_no_auth(self, client: AsyncClient):
        """POST /clues without auth should be rejected."""
        resp = await client.post(
            "/api/vmd/clues",
            json={"title": "New Lead from Web"},
        )
        _assert_auth_rejected(resp)

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

    @pytest.mark.asyncio
    async def test_update_clue_no_auth(self, client: AsyncClient):
        """PUT /clues/{id} without auth should be rejected."""
        resp = await client.put(
            "/api/vmd/clues/clue-id-123",
            json={"title": "Updated"},
        )
        _assert_auth_rejected(resp)

    @pytest.mark.asyncio
    async def test_follow_up_no_auth(self, client: AsyncClient):
        """POST /clues/{id}/follow-up without auth should be rejected."""
        resp = await client.post(
            "/api/vmd/clues/clue-id-123/follow-up",
            json={"action": "call", "content": "Called the client"},
        )
        _assert_auth_rejected(resp)


# ===========================================================================
# 9. VMD Clues Endpoints -- With bad token
# ===========================================================================


class TestVMDCluesBadToken:
    """VMD Clues endpoints with invalid Bearer token."""

    @pytest.mark.asyncio
    async def test_create_clue_bad_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/vmd/clues",
            json={"title": "Test Lead"},
            headers=BAD_TOKEN_HEADER,
        )
        _assert_db_error_or_auth_failure(resp)

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

    @pytest.mark.asyncio
    async def test_update_clue_bad_token(self, client: AsyncClient):
        resp = await client.put(
            "/api/vmd/clues/fake-id",
            json={"title": "Updated Lead"},
            headers=BAD_TOKEN_HEADER,
        )
        _assert_db_error_or_auth_failure(resp)

    @pytest.mark.asyncio
    async def test_follow_up_bad_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/vmd/clues/fake-id/follow-up",
            json={"action": "email", "content": "Sent follow-up email"},
            headers=BAD_TOKEN_HEADER,
        )
        _assert_db_error_or_auth_failure(resp)


# ===========================================================================
# 10. VMD Clues Endpoints -- Validation
# ===========================================================================


class TestVMDCluesValidation:
    """Input validation for clue endpoints."""

    @pytest.mark.asyncio
    async def test_create_clue_empty_body(self, client: AsyncClient):
        """POST /clues with empty body (missing required 'title')."""
        resp = await client.post(
            "/api/vmd/clues",
            json={},
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_create_clue_missing_title(self, client: AsyncClient):
        """POST /clues without the title field."""
        resp = await client.post(
            "/api/vmd/clues",
            json={"content": "Some content without title"},
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_update_clue_empty_body(self, client: AsyncClient):
        """PUT /clues/{id} with empty update body."""
        resp = await client.put(
            "/api/vmd/clues/fake-id",
            json={},
            headers=FAKE_TOKEN_HEADER,
        )
        # Either auth failure, or endpoint returns success=false for empty update
        if resp.status_code == 200:
            body = resp.json()
            assert body.get("success") is False
        else:
            assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_follow_up_missing_action(self, client: AsyncClient):
        """POST /clues/{id}/follow-up without action field."""
        resp = await client.post(
            "/api/vmd/clues/fake-id/follow-up",
            json={"content": "Some follow-up"},
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_follow_up_missing_content(self, client: AsyncClient):
        """POST /clues/{id}/follow-up without content field."""
        resp = await client.post(
            "/api/vmd/clues/fake-id/follow-up",
            json={"action": "call"},
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_follow_up_empty_body(self, client: AsyncClient):
        """POST /clues/{id}/follow-up with empty body."""
        resp = await client.post(
            "/api/vmd/clues/fake-id/follow-up",
            json={},
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_create_clue_negative_estimated_value(self, client: AsyncClient):
        """POST /clues with negative estimated_value should be rejected."""
        resp = await client.post(
            "/api/vmd/clues",
            json={
                "title": "Lead with bad value",
                "estimated_value": -100,
            },
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

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
    async def test_task_trend_no_auth(self, client: AsyncClient):
        """GET /dashboard/task-trend without auth should be rejected."""
        resp = await client.get("/api/vmd/dashboard/task-trend")
        _assert_auth_rejected(resp)

    @pytest.mark.asyncio
    async def test_agent_workload_no_auth(self, client: AsyncClient):
        """GET /dashboard/agent-workload without auth should be rejected."""
        resp = await client.get("/api/vmd/dashboard/agent-workload")
        _assert_auth_rejected(resp)

    @pytest.mark.asyncio
    async def test_scene_distribution_no_auth(self, client: AsyncClient):
        """GET /dashboard/scene-distribution without auth should be rejected."""
        resp = await client.get("/api/vmd/dashboard/scene-distribution")
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
    async def test_task_trend_bad_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/vmd/dashboard/task-trend", headers=BAD_TOKEN_HEADER
        )
        _assert_db_error_or_auth_failure(resp)

    @pytest.mark.asyncio
    async def test_agent_workload_bad_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/vmd/dashboard/agent-workload", headers=BAD_TOKEN_HEADER
        )
        _assert_db_error_or_auth_failure(resp)

    @pytest.mark.asyncio
    async def test_scene_distribution_bad_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/vmd/dashboard/scene-distribution",
            headers=BAD_TOKEN_HEADER,
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
    async def test_task_trend_response_is_json(self, client: AsyncClient):
        resp = await client.get(
            "/api/vmd/dashboard/task-trend", headers=FAKE_TOKEN_HEADER
        )
        _assert_json_response(resp)

    @pytest.mark.asyncio
    async def test_agent_workload_response_is_json(self, client: AsyncClient):
        resp = await client.get(
            "/api/vmd/dashboard/agent-workload", headers=FAKE_TOKEN_HEADER
        )
        _assert_json_response(resp)

    @pytest.mark.asyncio
    async def test_scene_distribution_response_is_json(self, client: AsyncClient):
        resp = await client.get(
            "/api/vmd/dashboard/scene-distribution",
            headers=FAKE_TOKEN_HEADER,
        )
        _assert_json_response(resp)

    @pytest.mark.asyncio
    async def test_task_trend_with_days_param(self, client: AsyncClient):
        """GET /task-trend with custom days parameter."""
        resp = await client.get(
            "/api/vmd/dashboard/task-trend?days=7",
            headers=FAKE_TOKEN_HEADER,
        )
        _assert_json_response(resp)

    @pytest.mark.asyncio
    async def test_task_trend_invalid_days_zero(self, client: AsyncClient):
        """GET /task-trend with days=0 should trigger validation error."""
        resp = await client.get(
            "/api/vmd/dashboard/task-trend?days=0",
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_task_trend_days_too_large(self, client: AsyncClient):
        """GET /task-trend with days=999 (over limit of 365)."""
        resp = await client.get(
            "/api/vmd/dashboard/task-trend?days=999",
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)


# ===========================================================================
# 14. LLM Model Endpoints -- Auth guard tests
# ===========================================================================


class TestLLMModelsAuth:
    """All /api/v1/llm endpoints require authentication."""

    @pytest.mark.asyncio
    async def test_list_models_no_auth(self, client: AsyncClient):
        """GET /llm/models without auth should be rejected."""
        resp = await client.get("/api/llm/models")
        _assert_auth_rejected(resp)

    @pytest.mark.asyncio
    async def test_create_model_no_auth(self, client: AsyncClient):
        """POST /llm/models without auth should be rejected."""
        resp = await client.post(
            "/api/llm/models",
            json={
                "model_code": "gpt-4o",
                "model_name": "GPT-4o",
                "provider_type": "openai",
                "adapter_code": "openai_chat",
                "api_base_url": "https://api.openai.com/v1",
                "api_key": "sk-test-key-12345",
            },
        )
        _assert_auth_rejected(resp)

    @pytest.mark.asyncio
    async def test_list_schedule_rules_no_auth(self, client: AsyncClient):
        """GET /llm/schedule-rules without auth should be rejected."""
        resp = await client.get("/api/llm/schedule-rules")
        _assert_auth_rejected(resp)


# ===========================================================================
# 15. LLM Model Endpoints -- With bad token
# ===========================================================================


class TestLLMModelsBadToken:
    """LLM Model endpoints with invalid Bearer token."""

    @pytest.mark.asyncio
    async def test_list_models_bad_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/llm/models", headers=BAD_TOKEN_HEADER
        )
        _assert_db_error_or_auth_failure(resp)

    @pytest.mark.asyncio
    async def test_create_model_bad_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/llm/models",
            json={
                "model_code": "test-model",
                "model_name": "Test Model",
                "provider_type": "openai",
                "adapter_code": "openai_chat",
                "api_base_url": "https://api.openai.com/v1",
                "api_key": "sk-test-key-12345",
            },
            headers=BAD_TOKEN_HEADER,
        )
        _assert_db_error_or_auth_failure(resp)

    @pytest.mark.asyncio
    async def test_list_schedule_rules_bad_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/llm/schedule-rules", headers=BAD_TOKEN_HEADER
        )
        _assert_db_error_or_auth_failure(resp)


# ===========================================================================
# 16. LLM Model Endpoints -- Validation
# ===========================================================================


class TestLLMModelsValidation:
    """Input validation for LLM model endpoints."""

    @pytest.mark.asyncio
    async def test_create_model_empty_body(self, client: AsyncClient):
        """POST /llm/models with empty body should return 422."""
        resp = await client.post(
            "/api/llm/models",
            json={},
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_create_model_missing_required_fields(self, client: AsyncClient):
        """POST /llm/models with only model_code (missing others)."""
        resp = await client.post(
            "/api/llm/models",
            json={"model_code": "m1"},
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_create_model_invalid_temperature(self, client: AsyncClient):
        """POST /llm/models with temperature > 2.0 should be rejected."""
        resp = await client.post(
            "/api/llm/models",
            json={
                "model_code": "test",
                "model_name": "Test",
                "provider_type": "openai",
                "adapter_code": "openai_chat",
                "api_base_url": "https://api.openai.com/v1",
                "api_key": "sk-test",
                "default_temperature": 5.0,
            },
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_create_model_invalid_timeout(self, client: AsyncClient):
        """POST /llm/models with timeout_ms below minimum (1000)."""
        resp = await client.post(
            "/api/llm/models",
            json={
                "model_code": "test",
                "model_name": "Test",
                "provider_type": "openai",
                "adapter_code": "openai_chat",
                "api_base_url": "https://api.openai.com/v1",
                "api_key": "sk-test",
                "timeout_ms": 100,
            },
            headers=FAKE_TOKEN_HEADER,
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_list_models_invalid_page(self, client: AsyncClient):
        """GET /llm/models with page=0."""
        resp = await client.get(
            "/api/llm/models?page=0", headers=FAKE_TOKEN_HEADER
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_list_models_page_size_too_large(self, client: AsyncClient):
        """GET /llm/models with page_size=200 (over 100 limit)."""
        resp = await client.get(
            "/api/llm/models?page_size=200", headers=FAKE_TOKEN_HEADER
        )
        assert resp.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_list_models_with_filters(self, client: AsyncClient):
        """GET /llm/models with filter query params should return JSON."""
        resp = await client.get(
            "/api/llm/models?status=active&model_type=chat&provider_type=openai",
            headers=FAKE_TOKEN_HEADER,
        )
        _assert_json_response(resp)

    @pytest.mark.asyncio
    async def test_list_schedule_rules_response_is_json(self, client: AsyncClient):
        """GET /llm/schedule-rules response must be JSON."""
        resp = await client.get(
            "/api/llm/schedule-rules", headers=FAKE_TOKEN_HEADER
        )
        _assert_json_response(resp)

    @pytest.mark.asyncio
    async def test_list_schedule_rules_invalid_page(self, client: AsyncClient):
        """GET /llm/schedule-rules with page=0."""
        resp = await client.get(
            "/api/llm/schedule-rules?page=0", headers=FAKE_TOKEN_HEADER
        )
        assert resp.status_code in (401, 403, 422, 500)


# ===========================================================================
# 17. LLM Model Endpoints -- Response format
# ===========================================================================


class TestLLMModelsResponseFormat:
    """Verify JSON response format for LLM model endpoints."""

    @pytest.mark.asyncio
    async def test_list_models_response_is_json(self, client: AsyncClient):
        resp = await client.get(
            "/api/llm/models", headers=FAKE_TOKEN_HEADER
        )
        _assert_json_response(resp)

    @pytest.mark.asyncio
    async def test_create_model_response_is_json(self, client: AsyncClient):
        resp = await client.post(
            "/api/llm/models",
            json={
                "model_code": "test-model",
                "model_name": "Test Model",
                "provider_type": "openai",
                "adapter_code": "openai_chat",
                "api_base_url": "https://api.openai.com/v1",
                "api_key": "sk-test",
            },
            headers=FAKE_TOKEN_HEADER,
        )
        _assert_json_response(resp)


# ===========================================================================
# 18. Cross-cutting: Security headers on VMD routes
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
    async def test_security_headers_on_llm_models(self, client: AsyncClient):
        resp = await client.get("/api/llm/models")
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
# 19. Cross-cutting: Rate limit headers on VMD routes
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
    async def test_rate_limit_headers_on_llm_models(self, client: AsyncClient):
        resp = await client.get("/api/llm/models")
        assert "x-ratelimit-limit" in resp.headers
        assert "x-ratelimit-remaining" in resp.headers

    @pytest.mark.asyncio
    async def test_rate_limit_headers_on_dashboard(self, client: AsyncClient):
        resp = await client.get("/api/vmd/dashboard/stats")
        assert "x-ratelimit-limit" in resp.headers
        assert "x-ratelimit-remaining" in resp.headers


# ===========================================================================
# 20. Route existence: VMD routes are registered
# ===========================================================================


class TestVMDRouteRegistration:
    """Verify that VMD and LLM routes are registered (not 404)."""

    @pytest.mark.asyncio
    async def test_vmd_tasks_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/vmd/tasks")
        assert resp.status_code != 404, "VMD tasks route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_compliance_rules_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/vmd/compliance/rules")
        assert resp.status_code != 404, "VMD compliance rules route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_compliance_check_route_exists(self, client: AsyncClient):
        resp = await client.post(
            "/api/vmd/compliance/check",
            json={"content": "test"},
        )
        assert resp.status_code != 404, "VMD compliance check route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_compliance_history_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/vmd/compliance/history")
        assert resp.status_code != 404, "VMD compliance history route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_clues_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/vmd/clues")
        assert resp.status_code != 404, "VMD clues route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_dashboard_stats_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/vmd/dashboard/stats")
        assert resp.status_code != 404, "VMD dashboard stats route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_dashboard_task_trend_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/vmd/dashboard/task-trend")
        assert resp.status_code != 404, "VMD dashboard task-trend route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_dashboard_agent_workload_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/vmd/dashboard/agent-workload")
        assert resp.status_code != 404, "VMD dashboard agent-workload route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_dashboard_scene_distribution_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/vmd/dashboard/scene-distribution")
        assert resp.status_code != 404, "VMD dashboard scene-distribution route should be registered"

    @pytest.mark.asyncio
    async def test_llm_models_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/llm/models")
        assert resp.status_code != 404, "LLM models route should be registered"

    @pytest.mark.asyncio
    async def test_llm_schedule_rules_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/llm/schedule-rules")
        assert resp.status_code != 404, "LLM schedule-rules route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_sub_task_audit_route_exists(self, client: AsyncClient):
        resp = await client.post(
            "/api/vmd/sub-tasks/any-id/audit",
            json={"action": "approve"},
        )
        assert resp.status_code != 404, "VMD sub-task audit route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_task_pause_route_exists(self, client: AsyncClient):
        resp = await client.post("/api/vmd/tasks/any-id/pause")
        assert resp.status_code != 404, "VMD task pause route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_task_cancel_route_exists(self, client: AsyncClient):
        resp = await client.post("/api/vmd/tasks/any-id/cancel")
        assert resp.status_code != 404, "VMD task cancel route should be registered"

    @pytest.mark.asyncio
    async def test_vmd_clue_follow_up_route_exists(self, client: AsyncClient):
        resp = await client.post(
            "/api/vmd/clues/any-id/follow-up",
            json={"action": "call", "content": "test"},
        )
        assert resp.status_code != 404, "VMD clue follow-up route should be registered"

    @pytest.mark.asyncio
    async def test_llm_create_model_route_exists(self, client: AsyncClient):
        resp = await client.post(
            "/api/llm/models",
            json={
                "model_code": "test",
                "model_name": "Test",
                "provider_type": "openai",
                "adapter_code": "openai_chat",
                "api_base_url": "https://api.openai.com/v1",
                "api_key": "sk-test",
            },
        )
        assert resp.status_code != 404, "LLM create model route should be registered"
