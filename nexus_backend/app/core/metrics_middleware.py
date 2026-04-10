"""
Item 44: Prometheus HTTP Metrics Collection Middleware

Collects HTTP request count and duration for Prometheus /metrics endpoint.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Paths to skip metrics collection (reduce noise)
_SKIP_PATHS = {
    "/",
    "/health",
    "/favicon.ico",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/redoc",
}


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Collects http_requests_total and http_request_duration_seconds."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _SKIP_PATHS:
            return await call_next(request)

        method = request.method
        start = time.perf_counter()

        response = await call_next(request)

        duration = time.perf_counter() - start

        # Lazy import to avoid circular imports at module level
        from app.core.metrics import observe_http_request

        observe_http_request(method, path, response.status_code, duration)

        return response
