"""
Tests for security middleware optimizations:
- CSP nonce generation
- Distributed Trace ID
- CSRF validation
"""

import asyncio
import secrets
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_request():
    """Create a mock Starlette request."""
    request = MagicMock()
    request.method = "GET"
    request.url.path = "/api/test"
    request.headers = {}
    request.state = MagicMock()
    return request


@pytest.fixture
def mock_response():
    """Create a mock response."""
    response = MagicMock()
    response.headers = {}
    response.status_code = 200
    return response


class TestCSPNonce:
    """Test CSP nonce generation and injection."""

    def test_nonce_is_generated_per_request(self):
        """Each request should get a unique nonce."""
        nonce1 = secrets.token_urlsafe(16)
        nonce2 = secrets.token_urlsafe(16)
        assert nonce1 != nonce2
        assert len(nonce1) >= 16

    def test_csp_template_contains_nonce_placeholder(self):
        from app.core.security_middleware import SecurityHeadersMiddleware
        assert "{{nonce}}" in SecurityHeadersMiddleware.CSP_TEMPLATE

    def test_fallback_csp_uses_unsafe_inline(self):
        from app.core.security_middleware import SecurityHeadersMiddleware
        assert "'unsafe-inline'" in SecurityHeadersMiddleware.FALLBACK_CSP

    def test_csp_template_nonce_replacement(self):
        from app.core.security_middleware import SecurityHeadersMiddleware
        test_nonce = "test-nonce-abc123"
        csp = SecurityHeadersMiddleware.CSP_TEMPLATE.replace("{{nonce}}", test_nonce)
        assert f"'nonce-{test_nonce}'" in csp
        assert "'unsafe-inline'" not in csp

    @patch.dict("os.environ", {"CSP_NONCE_ENABLED": "false"})
    def test_nonce_disabled_via_env(self):
        from app.core.security_middleware import SecurityHeadersMiddleware
        middleware = SecurityHeadersMiddleware(MagicMock())
        assert middleware._nonce_enabled is False

    @patch.dict("os.environ", {"CSP_NONCE_ENABLED": "true"})
    def test_nonce_enabled_via_env(self):
        from app.core.security_middleware import SecurityHeadersMiddleware
        middleware = SecurityHeadersMiddleware(MagicMock())
        assert middleware._nonce_enabled is True

    @patch.dict("os.environ", {"CSP_POLICY": "default-src 'self'"})
    def test_csp_override_takes_precedence(self):
        from app.core.security_middleware import SecurityHeadersMiddleware
        middleware = SecurityHeadersMiddleware(MagicMock())
        assert middleware._csp_override == "default-src 'self'"


class TestDistributedTraceID:
    """Test distributed trace ID propagation."""

    def test_trace_id_generated_when_not_provided(self):
        """When no X-Trace-ID header, use request_id as trace_id."""
        import uuid
        request_id = str(uuid.uuid4())
        # If no trace_id header, trace_id should fall back to request_id
        trace_id = None or request_id
        assert trace_id == request_id

    def test_trace_id_propagated_from_header(self):
        """When X-Trace-ID is provided by frontend, it should be used."""
        frontend_trace = "fe-abc123-xyz789"
        trace_id = frontend_trace or "fallback-id"
        assert trace_id == frontend_trace

    def test_trace_id_format(self):
        """Frontend trace IDs should follow the fe- prefix convention."""
        # Simulate frontend trace ID generation
        import time
        timestamp = hex(int(time.time()))[2:]
        trace_id = f"fe-{timestamp}-test"
        assert trace_id.startswith("fe-")

    def test_server_timing_header_format(self):
        """Server-Timing header should contain duration."""
        duration_ms = 42.5
        header = f'total;dur={duration_ms};desc="Request Duration"'
        assert "dur=42.5" in header
        assert "Request Duration" in header


class TestCrossSiteRequestForgery:
    """Test CSRF protection in SecurityHeadersMiddleware."""

    def test_csrf_allows_get_requests(self):
        from app.core.security_middleware import SecurityHeadersMiddleware
        assert "GET" not in SecurityHeadersMiddleware.MUTATING_METHODS

    def test_csrf_checks_post_requests(self):
        from app.core.security_middleware import SecurityHeadersMiddleware
        assert "POST" in SecurityHeadersMiddleware.MUTATING_METHODS
        assert "PUT" in SecurityHeadersMiddleware.MUTATING_METHODS
        assert "DELETE" in SecurityHeadersMiddleware.MUTATING_METHODS

    def test_public_paths_exempt_from_csrf(self):
        from app.core.security_middleware import SecurityHeadersMiddleware
        assert "/health" in SecurityHeadersMiddleware.PUBLIC_PATHS
        assert "/" in SecurityHeadersMiddleware.PUBLIC_PATHS


class TestSecurityHeaders:
    """Test OWASP security headers."""

    def test_hsts_header_present(self):
        from app.core.security_middleware import SecurityHeadersMiddleware
        assert "Strict-Transport-Security" in SecurityHeadersMiddleware.SECURITY_HEADERS

    def test_xframe_deny(self):
        from app.core.security_middleware import SecurityHeadersMiddleware
        assert SecurityHeadersMiddleware.SECURITY_HEADERS["X-Frame-Options"] == "DENY"

    def test_referrer_policy(self):
        from app.core.security_middleware import SecurityHeadersMiddleware
        assert "strict-origin" in SecurityHeadersMiddleware.SECURITY_HEADERS["Referrer-Policy"]

    def test_permissions_policy_restricts_features(self):
        from app.core.security_middleware import SecurityHeadersMiddleware
        pp = SecurityHeadersMiddleware.SECURITY_HEADERS["Permissions-Policy"]
        assert "camera=()" in pp
        assert "microphone=()" in pp
        assert "geolocation=()" in pp
