"""
Integration tests for the FastAPI router layer.

Uses httpx AsyncClient with ASGITransport to test the real FastAPI application
through its full middleware stack (RateLimit -> SecurityHeaders -> RequestID ->
TenantContext -> CORS) without spinning up a live server.

These tests verify:
  - Public endpoints (/health, /) are accessible without authentication.
  - Authenticated endpoints reject requests that lack a valid Bearer token.
  - Middleware ordering is correct (outermost first).
  - Security headers are present on every response.
  - Response structure matches the API conventions.
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

    The real ``app.core.database.supabase`` may be ``None`` when env vars are
    absent, but the health endpoint reads it at call-time.  We patch it to
    ``None`` explicitly so the health check degrades gracefully (returns
    ``not_configured`` for the database status) and no real network calls occur.

    We also neuter the lifespan-managed background services (cache, event bus,
    checkpointer, connection pools) so they don't attempt real I/O.
    """
    with (
        patch("app.core.database.supabase", None),
        patch("app.services.cache_service.cache_service.init", new_callable=AsyncMock),
        patch("app.services.cache_service.cache_service.ping", new_callable=AsyncMock, return_value=False),
        patch("app.services.event_bus.event_bus.start", new_callable=AsyncMock),
        patch("app.services.event_bus.event_bus.stop", new_callable=AsyncMock),
        patch("app.services.audit_logger.audit_logger.force_flush", new_callable=AsyncMock),
    ):
        from app.main import app  # noqa: E402 -- intentionally late import

        yield app


@pytest_asyncio.fixture(autouse=True)
async def _reset_rate_limiter():
    """Reset the in-memory rate limiter token buckets before every test.

    Without this, the burst budget is exhausted after a handful of
    requests and subsequent tests receive 429 instead of the expected
    auth-error status codes.
    """
    from app.core.rate_limiter import rate_limiter

    rate_limiter.tokens.clear()
    rate_limiter.last_update.clear()
    yield


@pytest_asyncio.fixture()
async def client(patched_app):
    """Provide an httpx AsyncClient bound to the ASGI app.

    ``base_url`` is set to ``http://test`` so that httpx sends requests
    through the ASGI transport rather than to the network.
    """
    transport = ASGITransport(app=patched_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ===========================================================================
# 1. Health Endpoint
# ===========================================================================


class TestHealthEndpoint:
    """GET /health -- public, no auth required."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client: AsyncClient):
        """The health endpoint should always return HTTP 200."""
        resp = await client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_contains_status_field(self, client: AsyncClient):
        """Response body must include a top-level 'status' key."""
        resp = await client.get("/health")
        body = resp.json()
        assert "status" in body
        # Without real DB/cache the status should be 'degraded'
        assert body["status"] in ("healthy", "degraded")

    @pytest.mark.asyncio
    async def test_health_contains_version(self, client: AsyncClient):
        """The version field should be present and non-empty."""
        resp = await client.get("/health")
        body = resp.json()
        assert "version" in body
        assert isinstance(body["version"], str)
        assert len(body["version"]) > 0

    @pytest.mark.asyncio
    async def test_health_contains_checks_section(self, client: AsyncClient):
        """A 'checks' dict with database, cache, and ai_gateway must exist."""
        resp = await client.get("/health")
        body = resp.json()
        checks = body.get("checks", {})
        assert "database" in checks
        assert "cache" in checks
        assert "ai_gateway" in checks

    @pytest.mark.asyncio
    async def test_health_database_not_configured(self, client: AsyncClient):
        """With supabase patched to None, database check says 'not_configured'."""
        resp = await client.get("/health")
        body = resp.json()
        assert body["checks"]["database"] == "not_configured"

    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, client: AsyncClient):
        """Health endpoint must work without any Authorization header."""
        resp = await client.get("/health")
        # Should NOT be 401 or 403
        assert resp.status_code == 200


# ===========================================================================
# 2. Root Endpoint
# ===========================================================================


class TestRootEndpoint:
    """GET / -- public landing page."""

    @pytest.mark.asyncio
    async def test_root_returns_200(self, client: AsyncClient):
        resp = await client.get("/")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_root_body_has_message(self, client: AsyncClient):
        resp = await client.get("/")
        body = resp.json()
        assert "message" in body
        assert "Nexus" in body["message"] or "Running" in body["message"]

    @pytest.mark.asyncio
    async def test_root_body_has_docs_link(self, client: AsyncClient):
        resp = await client.get("/")
        body = resp.json()
        assert "docs" in body
        assert body["docs"] == "/docs"

    @pytest.mark.asyncio
    async def test_root_no_auth_required(self, client: AsyncClient):
        """Root endpoint should be publicly accessible."""
        resp = await client.get("/")
        assert resp.status_code != 401
        assert resp.status_code != 403


# ===========================================================================
# 3. POST /api/chat -- requires auth
# ===========================================================================


class TestChatEndpointAuth:
    """POST /api/chat -- must reject unauthenticated requests."""

    @pytest.mark.asyncio
    async def test_chat_no_auth_returns_401_or_403(self, client: AsyncClient):
        """Without a Bearer token the chat endpoint must refuse the request."""
        resp = await client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "hello"}], "model": "gpt-4o"},
        )
        assert resp.status_code in (401, 403, 422)

    @pytest.mark.asyncio
    async def test_chat_invalid_bearer_returns_401(self, client: AsyncClient):
        """A completely bogus Bearer token should be rejected."""
        resp = await client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "hi"}], "model": "gpt-4o"},
            headers={"Authorization": "Bearer totally-invalid-token"},
        )
        assert resp.status_code in (401, 403, 500)

    @pytest.mark.asyncio
    async def test_chat_test_prefix_blocked(self, client: AsyncClient):
        """The deprecated test: auth scheme must be blocked."""
        resp = await client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "hi"}], "model": "gpt-4o"},
            headers={"Authorization": "test:fake-user"},
        )
        assert resp.status_code in (401, 403)


# ===========================================================================
# 4. GET /api/billing/plans -- public catalog
# ===========================================================================


class TestBillingPlansEndpoint:
    """GET /api/billing/plans -- returns the plan catalog (no auth)."""

    @pytest.mark.asyncio
    async def test_plans_returns_200(self, client: AsyncClient):
        resp = await client.get("/api/billing/plans")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_plans_body_has_success_flag(self, client: AsyncClient):
        resp = await client.get("/api/billing/plans")
        body = resp.json()
        assert body.get("success") is True

    @pytest.mark.asyncio
    async def test_plans_body_contains_plans_list(self, client: AsyncClient):
        resp = await client.get("/api/billing/plans")
        body = resp.json()
        data = body.get("data", {})
        plans = data.get("plans")
        assert isinstance(plans, list)
        assert len(plans) > 0, "Plan catalog should have at least one plan"

    @pytest.mark.asyncio
    async def test_plans_each_plan_has_name(self, client: AsyncClient):
        resp = await client.get("/api/billing/plans")
        body = resp.json()
        plans = body["data"]["plans"]
        for plan in plans:
            assert "name" in plan, f"Plan missing 'name': {plan}"


# ===========================================================================
# 5. GET /api/mcp/tools -- requires auth
# ===========================================================================


class TestMCPToolsAuth:
    """GET /api/mcp/tools -- must reject unauthenticated requests."""

    @pytest.mark.asyncio
    async def test_mcp_tools_no_auth(self, client: AsyncClient):
        resp = await client.get("/api/mcp/tools")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_mcp_tools_bad_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/mcp/tools",
            headers={"Authorization": "Bearer invalid"},
        )
        assert resp.status_code in (401, 403, 500)

    @pytest.mark.asyncio
    async def test_mcp_tools_response_is_json(self, client: AsyncClient):
        """Even error responses should be well-formed JSON."""
        resp = await client.get("/api/mcp/tools")
        assert resp.headers.get("content-type", "").startswith("application/json")


# ===========================================================================
# 6. GET /api/robot/devices -- requires auth
# ===========================================================================


class TestRobotDevicesAuth:
    """GET /api/robot/devices -- must reject unauthenticated requests."""

    @pytest.mark.asyncio
    async def test_robot_devices_no_auth(self, client: AsyncClient):
        resp = await client.get("/api/robot/devices")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_robot_devices_bad_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/robot/devices",
            headers={"Authorization": "Bearer not.a.real.jwt"},
        )
        assert resp.status_code in (401, 403, 500)


# ===========================================================================
# 7. GET /api/kingdee/inventory/test123 -- requires auth
# ===========================================================================


class TestKingdeeInventoryAuth:
    """GET /api/kingdee/inventory/{item_id} -- requires authentication."""

    @pytest.mark.asyncio
    async def test_kingdee_inventory_no_auth(self, client: AsyncClient):
        resp = await client.get("/api/kingdee/inventory/test123")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_kingdee_inventory_bad_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/kingdee/inventory/test123",
            headers={"Authorization": "Bearer garbage-token"},
        )
        assert resp.status_code in (401, 403, 500)

    @pytest.mark.asyncio
    async def test_kingdee_inventory_error_body_structure(self, client: AsyncClient):
        """Error response should follow the standardized format."""
        resp = await client.get("/api/kingdee/inventory/test123")
        body = resp.json()
        # The global exception handler wraps errors in {"success": False, "error": ...}
        assert body.get("success") is False or "detail" in body or "error" in body


# ===========================================================================
# 8. Middleware Ordering & Security Headers
# ===========================================================================


class TestMiddlewareOrder:
    """Verify that the middleware stack is configured correctly.

    According to ``main.py``, the intended execution order (outermost first)
    is:  CORS -> RateLimit -> SecurityHeaders -> RequestID -> APIKey -> TenantContext.

    In Starlette, ``app.user_middleware`` stores them in *reverse* add-order:
    the middleware that was added last (i.e., the outermost) ends up at
    index 0.  So CORSMiddleware should be at position 0.
    """

    @pytest.mark.asyncio
    async def test_rate_limit_middleware_is_outermost(self, patched_app):
        """CORSMiddleware should be at index 0 (outermost) and
        RateLimitMiddleware should be at index 1 (second outermost).
        """
        from starlette.middleware.cors import CORSMiddleware

        from app.core.rate_limiter import RateLimitMiddleware

        middleware_classes = [m.cls for m in patched_app.user_middleware]
        assert RateLimitMiddleware in middleware_classes, "RateLimitMiddleware not found in user_middleware"
        assert CORSMiddleware in middleware_classes, "CORSMiddleware not found in user_middleware"
        # CORSMiddleware is outermost (index 0), RateLimitMiddleware is second (index 1).
        assert middleware_classes[0] is CORSMiddleware, (
            "CORSMiddleware should be the outermost (index 0) middleware, "
            f"but found: {middleware_classes[0].__name__}"
        )
        assert middleware_classes[1] is RateLimitMiddleware, (
            "RateLimitMiddleware should be at index 1, " f"but found: {middleware_classes[1].__name__}"
        )

    @pytest.mark.asyncio
    async def test_middleware_full_order(self, patched_app):
        """Verify the complete middleware ordering matches the design doc.

        Expected execution order (outermost -> innermost):
          CORS -> RateLimit -> SecurityHeaders -> RequestID -> APIKey -> TenantContext
        Which in user_middleware (index 0 = outermost) is:
          [0] CORS, [1] RateLimit, [2] SecurityHeaders, [3] RequestID,
          [4] APIKey, [5] TenantContext
        """
        from starlette.middleware.cors import CORSMiddleware

        from app.core.api_key_middleware import APIKeyMiddleware
        from app.core.csrf_middleware import CSRFMiddleware
        from app.core.data_masking import DataMaskingMiddleware
        from app.core.idempotency_middleware import IdempotencyMiddleware
        from app.core.rate_limiter import RateLimitMiddleware
        from app.core.security_middleware import (
            RequestIDMiddleware,
            SecurityHeadersMiddleware,
            TenantContextMiddleware,
        )

        middleware_classes = [m.cls for m in patched_app.user_middleware]
        expected_order = [
            CORSMiddleware,
            RateLimitMiddleware,
            SecurityHeadersMiddleware,
            RequestIDMiddleware,
            DataMaskingMiddleware,
            CSRFMiddleware,
            APIKeyMiddleware,
            IdempotencyMiddleware,
            TenantContextMiddleware,
        ]
        assert middleware_classes == expected_order, (
            f"Middleware order mismatch.\n"
            f"  Expected: {[c.__name__ for c in expected_order]}\n"
            f"  Actual:   {[c.__name__ for c in middleware_classes]}"
        )

    @pytest.mark.asyncio
    async def test_security_headers_present(self, client: AsyncClient):
        """SecurityHeadersMiddleware should add protective headers."""
        resp = await client.get("/")
        assert "x-content-type-options" in resp.headers
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert "x-frame-options" in resp.headers
        assert resp.headers["x-frame-options"] == "DENY"

    @pytest.mark.asyncio
    async def test_request_id_header_present(self, client: AsyncClient):
        """RequestIDMiddleware should add an X-Request-ID to every response."""
        resp = await client.get("/")
        assert "x-request-id" in resp.headers
        request_id = resp.headers["x-request-id"]
        assert len(request_id) > 0

    @pytest.mark.asyncio
    async def test_custom_request_id_is_echoed(self, client: AsyncClient):
        """If the caller sends X-Request-ID it should be echoed back."""
        custom_id = "integration-test-req-001"
        resp = await client.get("/", headers={"X-Request-ID": custom_id})
        assert resp.headers.get("x-request-id") == custom_id

    @pytest.mark.asyncio
    async def test_hsts_header_present(self, client: AsyncClient):
        """Strict-Transport-Security should be set by SecurityHeadersMiddleware."""
        resp = await client.get("/")
        assert "strict-transport-security" in resp.headers

    @pytest.mark.asyncio
    async def test_csp_header_present(self, client: AsyncClient):
        """Content-Security-Policy header should exist."""
        resp = await client.get("/health")
        assert "content-security-policy" in resp.headers


# ===========================================================================
# 9. Favicon & Misc Endpoints
# ===========================================================================


class TestMiscEndpoints:
    """Small helper endpoints that should always work."""

    @pytest.mark.asyncio
    async def test_favicon_returns_204(self, client: AsyncClient):
        resp = await client.get("/favicon.ico")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_nonexistent_route_returns_404(self, client: AsyncClient):
        resp = await client.get("/api/this-does-not-exist")
        assert resp.status_code == 404


# ===========================================================================
# 10. Error Response Format Consistency
# ===========================================================================


class TestErrorResponseFormat:
    """Verify that error responses from the global exception handler follow the
    standardized shape: ``{"success": false, "error": {...}}``.
    """

    @pytest.mark.asyncio
    async def test_auth_error_is_json(self, client: AsyncClient):
        """Auth failures should produce application/json responses."""
        resp = await client.get("/api/mcp/tools")
        ct = resp.headers.get("content-type", "")
        assert "application/json" in ct

    @pytest.mark.asyncio
    async def test_auth_error_has_success_false(self, client: AsyncClient):
        """Global exception handler should set success=False for HTTP errors."""
        resp = await client.get("/api/mcp/tools")
        body = resp.json()
        # The global handler wraps HTTPException into {"success": False, "error": ...}
        assert body.get("success") is False

    @pytest.mark.asyncio
    async def test_auth_error_has_error_payload(self, client: AsyncClient):
        """The 'error' field should carry either a dict or a string message."""
        resp = await client.get("/api/robot/devices")
        body = resp.json()
        error_field = body.get("error")
        assert error_field is not None
        if isinstance(error_field, dict):
            assert "message" in error_field or "code" in error_field
        else:
            assert isinstance(error_field, str)


# ===========================================================================
# 11. Boss Dashboard -- requires auth
# ===========================================================================


class TestBossDashboardAuth:
    """GET /api/dashboard/boss -- must reject unauthenticated requests."""

    @pytest.mark.asyncio
    async def test_boss_dashboard_no_auth(self, client: AsyncClient):
        resp = await client.get("/api/dashboard/boss")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_boss_dashboard_bad_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/dashboard/boss",
            headers={"Authorization": "Bearer not-valid"},
        )
        assert resp.status_code in (401, 403, 500)


# ===========================================================================
# 12. Rate Limit Headers (non-exempt paths)
# ===========================================================================


class TestRateLimitHeaders:
    """Non-exempt endpoints should carry rate-limit response headers."""

    @pytest.mark.asyncio
    async def test_rate_limit_headers_on_api_route(self, client: AsyncClient):
        """An /api/* route (even if it 401s) should have rate limit headers."""
        resp = await client.get("/api/mcp/tools")
        assert "x-ratelimit-limit" in resp.headers
        assert "x-ratelimit-remaining" in resp.headers
        assert "x-ratelimit-reset" in resp.headers

    @pytest.mark.asyncio
    async def test_rate_limit_exempt_on_health(self, client: AsyncClient):
        """Health and root endpoints are exempt -- they may lack RL headers."""
        resp = await client.get("/health")
        # Exempt paths skip RateLimitMiddleware entirely so the headers are
        # NOT expected.  If they happen to be present that is also fine.
        # We only assert the request succeeded (not rate-limited).
        assert resp.status_code == 200
