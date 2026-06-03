"""
P2 Security: Security Headers Middleware

Adds security headers to all responses to prevent common web vulnerabilities:
- XSS (Cross-Site Scripting)
- Clickjacking
- MIME type sniffing
- Information disclosure
"""

import logging
import os
import secrets
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all HTTP responses.

    These headers help protect against various web vulnerabilities
    and are recommended by OWASP security guidelines.

    Features:
    - Configurable CSP via CSP_POLICY environment variable
    - CSRF origin validation on mutating requests (POST, PUT, PATCH, DELETE)
    - Standard OWASP security headers
    """

    # CSP policy template with nonce placeholder.
    # When CSP_NONCE_ENABLED=true (default), {nonce_placeholder} is replaced
    # per-request with a fresh cryptographic nonce, eliminating 'unsafe-inline'.
    # When disabled or overridden via CSP_POLICY env var, falls back gracefully.
    CSP_TEMPLATE = (
        "default-src 'self'; "
        "script-src 'self' 'nonce-{{nonce}}' https://*.zeabur.app; "
        "style-src 'self' 'nonce-{{nonce}}' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://*.supabase.co https://*.flydao.top;"
    )

    # Fallback CSP for environments where nonce injection is not possible
    FALLBACK_CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://*.zeabur.app; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://*.supabase.co https://*.flydao.top;"
    )

    # Default security headers (CSP is added dynamically in dispatch)
    SECURITY_HEADERS = {
        # Prevent XSS attacks
        "X-Content-Type-Options": "nosniff",
        # Prevent clickjacking
        "X-Frame-Options": "DENY",
        # Enable XSS filter in browsers
        "X-XSS-Protection": "1; mode=block",
        # Referrer policy for privacy
        "Referrer-Policy": "strict-origin-when-cross-origin",
        # Prevent MIME type sniffing
        "Content-Type-Options": "nosniff",
        # Cache control for sensitive data
        "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
        "Pragma": "no-cache",
        # Permissions policy (restrict browser features)
        "Permissions-Policy": "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()",
        # P0 Security: HSTS (Strict-Transport-Security)
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    }

    # Paths that may need different caching
    STATIC_PATHS = {"/docs", "/redoc", "/openapi.json", "/favicon.ico"}

    # Public paths exempt from CSRF validation (mirrors TenantContextMiddleware)
    PUBLIC_PATHS = {
        "/",
        "/health",
        "/favicon.ico",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/test-ai",
    }

    # HTTP methods that mutate state and require CSRF origin checks
    MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(self, app) -> None:
        super().__init__(app)
        # Configurable CSP: prefer CSP_POLICY env var (static), else use nonce template
        self._csp_override = os.environ.get("CSP_POLICY")
        self._nonce_enabled = (
            os.environ.get("CSP_NONCE_ENABLED", "true").lower() == "true"
        )
        # Configurable allowed origins for CSRF validation
        raw_origins = os.environ.get(
            "ALLOWED_ORIGINS",
            "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173,"
            "https://aizk.flydao.top,https://*.flydao.top,https://*.zeabur.app",
        )
        self._allowed_origins: set[str] = set()
        self._allowed_wildcard_suffixes: list[str] = []
        for o in raw_origins.split(","):
            o = o.strip().rstrip("/").lower()
            if not o:
                continue
            if "://*." in o:
                # e.g. "https://*.flydao.top" -> match any subdomain
                # Extract the suffix after the wildcard: ".flydao.top"
                scheme_end = o.index("://")
                suffix = o[scheme_end + 4 :]  # skip "://*"
                scheme = o[: scheme_end + 3]  # "https://"
                self._allowed_wildcard_suffixes.append((scheme, suffix))
            else:
                self._allowed_origins.add(o)

    # ------------------------------------------------------------------
    # CSRF Origin Validation
    # ------------------------------------------------------------------
    def _origin_allowed(self, normalised: str) -> bool:
        """Check if origin is in the allowed list (exact or wildcard)."""
        if normalised in self._allowed_origins:
            return True
        for scheme, suffix in self._allowed_wildcard_suffixes:
            if normalised.startswith(scheme) and normalised.endswith(suffix):
                return True
        return False

    def _validate_csrf_origin(self, request: Request) -> JSONResponse | None:
        """Validate Origin/Referer on mutating requests.

        Returns a 403 JSONResponse if validation fails, or None if the
        request is allowed to proceed.
        """
        if request.method not in self.MUTATING_METHODS:
            return None

        if request.url.path in self.PUBLIC_PATHS:
            return None

        # Prefer Origin header; fall back to Referer
        origin = request.headers.get("origin")
        if not origin:
            referer = request.headers.get("referer")
            if referer:
                parsed = urlparse(referer)
                origin = f"{parsed.scheme}://{parsed.netloc}"

        # If no Origin/Referer at all, allow the request through — this
        # accommodates non-browser clients (curl, Postman, mobile SDKs).
        if not origin:
            return None

        normalised = origin.strip().rstrip("/").lower()
        if not self._origin_allowed(normalised):
            logger.warning(
                "CSRF validation failed: origin %s not in allowed list", origin
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF validation failed: origin not allowed"},
            )

        return None

    async def dispatch(self, request: Request, call_next) -> Response:
        # --- CSRF check (before processing the request) ---
        csrf_error = self._validate_csrf_origin(request)
        if csrf_error is not None:
            return csrf_error

        # Generate per-request CSP nonce
        nonce = secrets.token_urlsafe(16) if self._nonce_enabled else None
        if nonce:
            request.state.csp_nonce = nonce

        response = await call_next(request)

        # Add security headers to all responses
        for header_name, header_value in self.SECURITY_HEADERS.items():
            # Don't override if already set
            if header_name not in response.headers:
                response.headers[header_name] = header_value

        # Add CSP header: nonce-based (secure) or fallback
        if "Content-Security-Policy" not in response.headers:
            if self._csp_override:
                response.headers["Content-Security-Policy"] = self._csp_override
            elif nonce:
                response.headers["Content-Security-Policy"] = self.CSP_TEMPLATE.replace(
                    "{{nonce}}", nonce
                )
            else:
                response.headers["Content-Security-Policy"] = self.FALLBACK_CSP

        # Allow caching for static/documentation paths
        if request.url.path in self.STATIC_PATHS or request.url.path.endswith(
            (".png", ".ico", ".svg", ".webp", ".webmanifest")
        ):
            response.headers["Cache-Control"] = "public, max-age=3600"

        return response


class UnhandledExceptionMiddleware:
    """Catch unexpected downstream errors before Starlette logs middleware noise.

    BaseHTTPMiddleware wraps each `call_next` layer, so one route exception can
    produce a very long stack trace through every middleware. This ASGI-level
    guard logs the real request context once and returns the same safe JSON
    shape as the global exception handler.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            if response_started:
                raise

            request = Request(scope, receive=receive)
            trace_id = (
                getattr(request.state, "trace_id", None)
                or request.headers.get("X-Trace-ID")
                or request.headers.get("X-Request-ID")
                or ""
            )
            logger.error(
                "Unhandled request exception: %s | path=%s method=%s trace_id=%s",
                exc,
                scope.get("path", ""),
                scope.get("method", ""),
                trace_id,
                exc_info=True,
            )

            error_body: dict = {
                "code": "SYSTEM_INTERNAL_ERROR",
                "message": "系统内部错误，请稍后重试",
            }
            if trace_id:
                error_body["trace_id"] = trace_id

            response = JSONResponse(
                status_code=500,
                content={"success": False, "error": error_body},
            )
            await response(scope, receive, send)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add a unique request/trace ID to each request.

    Supports distributed tracing by propagating a single Trace ID from
    frontend → API → database queries → audit logs.

    Headers:
    - X-Request-ID: Unique per-request identifier
    - X-Trace-ID: End-to-end trace identifier (can be set by frontend)
    - Server-Timing: Includes traceId for browser DevTools visibility
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        import time
        import uuid

        from app.core.trace_context import set_request_id, set_trace_id

        request_start = time.monotonic()

        # Check if request ID already provided (e.g., from load balancer)
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Trace ID: propagate from frontend or generate new
        trace_id = request.headers.get("X-Trace-ID") or request_id

        # Store in request state for access in route handlers and services
        request.state.request_id = request_id
        request.state.trace_id = trace_id

        # #25: 设置 ContextVar 使得任何服务层都能获取 trace_id
        set_trace_id(trace_id)
        set_request_id(request_id)

        # Process request
        response = await call_next(request)

        duration_ms = round((time.monotonic() - request_start) * 1000, 2)

        # Add tracing headers to response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-ID"] = trace_id
        response.headers["Server-Timing"] = (
            f'total;dur={duration_ms};desc="Request Duration"'
        )

        # Structured log with trace context for log aggregation
        logger.info(
            "request_completed",
            extra={
                "trace_id": trace_id,
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "user_id": getattr(request.state, "user_id", None),
            },
        )

        return response


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject tenant context (org_id) into the request.

    P0 Multi-tenancy:
    - Extracts User ID from JWT
    - Injects Scoped Supabase client (activating RLS)
    - Prevents cross-tenant data leaks
    """

    # Paths that never need tenant context (public endpoints)
    PUBLIC_PATHS = {
        "/",
        "/health",
        "/favicon.ico",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/test-ai",
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        from app.core.auth import get_current_user_id
        from app.core.database import supabase
        from app.services.cache_service import cache_service

        # If API Key middleware already authenticated, skip JWT flow
        if getattr(request.state, "api_key_auth", False):
            return await call_next(request)

        # Initialize default state
        request.state.user_id = None
        request.state.org_id = None
        request.state.auth_failed = False

        # P0 Security Fix: Do NOT default to global service-key client.
        # Only public endpoints get the global client; authenticated routes
        # get a scoped client or None (forcing 401 at the route level).
        if request.url.path in self.PUBLIC_PATHS:
            request.state.db = supabase
        else:
            request.state.db = None  # Force routes to check auth

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                # 1. Authenticate user
                user_id = await get_current_user_id(
                    request=request, authorization=auth_header
                )
                request.state.user_id = user_id

                # 2. Get Org ID (with caching, TTL reduced to 5 min)
                # Security: mutating methods skip cache to ensure
                # permission revocations take effect immediately.
                is_mutating = request.method in ("POST", "PUT", "PATCH", "DELETE")
                cache_key = f"user:{user_id}:org_id"
                org_id = None if is_mutating else await cache_service.get(cache_key)

                if not org_id:
                    # Query once from users table - P0 Fix: Use organization_id
                    res = (
                        await supabase.table("users")
                        .select("organization_id")
                        .eq("id", user_id)
                        .maybe_single()
                        .execute()
                    )
                    if res.data:
                        org_id = res.data.get("organization_id")
                        if org_id:
                            await cache_service.set(cache_key, org_id, ttl=300)

                request.state.org_id = org_id

                # 3. Inject Scoped Client (Activate RLS)
                # P0 Security Fix: service_key clients bypass RLS.
                # Scoped client uses the user's JWT to ensure SQL-level RLS is enforced.
                token = auth_header.split(" ")[1]
                request.state.db = supabase.get_scoped_client(token)

            except Exception as e:
                # P0 Security Fix: Do NOT fallback to global service-key client.
                # Set db=None so route-level auth checks will reject the request.
                request.state.db = None
                request.state.auth_failed = True
                logger.warning(
                    f"TenantMiddleware: Auth failed, RLS client not created: {e}"
                )

        return await call_next(request)
