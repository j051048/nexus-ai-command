"""
P2 Security: Security Headers Middleware

Adds security headers to all responses to prevent common web vulnerabilities:
- XSS (Cross-Site Scripting)
- Clickjacking
- MIME type sniffing
- Information disclosure
"""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all HTTP responses.

    These headers help protect against various web vulnerabilities
    and are recommended by OWASP security guidelines.
    """

    # Default security headers
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
        # P1 Security: Content Security Policy
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline' https://*.zeabur.app; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://*.supabase.co https://*.flydao.top;",
        # P0 Security: HSTS (Strict-Transport-Security)
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    }

    # Paths that may need different caching
    STATIC_PATHS = {"/docs", "/redoc", "/openapi.json", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Add security headers to all responses
        for header_name, header_value in self.SECURITY_HEADERS.items():
            # Don't override if already set
            if header_name not in response.headers:
                response.headers[header_name] = header_value

        # Allow caching for static/documentation paths
        if request.url.path in self.STATIC_PATHS:
            response.headers["Cache-Control"] = "public, max-age=3600"

        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add a unique request ID to each request.

    Useful for tracing requests across logs and services.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        import uuid

        # Check if request ID already provided (e.g., from load balancer)
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Store in request state for access in route handlers
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

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
    PUBLIC_PATHS = {"/", "/health", "/favicon.ico", "/docs", "/redoc", "/openapi.json", "/api/test-ai"}

    async def dispatch(self, request: Request, call_next) -> Response:
        from app.core.database import supabase
        from app.core.auth import get_current_user_id
        from app.services.cache_service import cache_service

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
                user_id = await get_current_user_id(auth_header)
                request.state.user_id = user_id

                # 2. Get Org ID (with caching, TTL reduced to 5 min)
                cache_key = f"user:{user_id}:org_id"
                org_id = await cache_service.get(cache_key)

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
                logger.warning(f"TenantMiddleware: Auth failed, RLS client not created: {e}")

        return await call_next(request)
