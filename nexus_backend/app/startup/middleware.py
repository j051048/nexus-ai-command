"""Middleware registration — order matters (last added = outermost)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.rate_limiter import RateLimitMiddleware
from app.core.security_middleware import (
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
    TenantContextMiddleware,
    UnhandledExceptionMiddleware,
)


def register_middleware(app: FastAPI) -> None:
    """Register all middleware in correct order.

    P0 Security Fix: Middleware order matters - last added runs first (outermost).
    Execution order (outermost -> innermost):
      CORS -> UnhandledException -> Metrics -> RateLimit -> SecurityHeaders -> RequestID
      -> DataMasking -> CSRF -> APIKey -> Idempotency -> TenantContext

    CORS MUST be outermost so browser preflight (OPTIONS) is handled immediately
    before any auth/rate-limit middleware rejects the request.
    """
    from app.core.api_key_middleware import APIKeyMiddleware
    from app.core.csrf_middleware import CSRFMiddleware
    from app.core.data_masking import DataMaskingMiddleware
    from app.core.idempotency_middleware import IdempotencyMiddleware
    from app.core.metrics_middleware import PrometheusMiddleware

    # 10th (innermost): sets up tenant DB scope
    app.add_middleware(TenantContextMiddleware)
    # 9th: idempotency dedup for write operations
    app.add_middleware(IdempotencyMiddleware)
    # 8th: API Key auth sets org_id before tenant context
    app.add_middleware(APIKeyMiddleware)
    # 7th: CSRF protection for cookie-based auth
    app.add_middleware(CSRFMiddleware)
    # 6th: auto-mask sensitive fields in responses
    app.add_middleware(DataMaskingMiddleware)
    # 5th: adds request tracing ID + sets contextvars
    app.add_middleware(RequestIDMiddleware)
    # 4th: security response headers
    app.add_middleware(SecurityHeadersMiddleware)
    # 3rd: blocks abuse BEFORE DB queries
    app.add_middleware(RateLimitMiddleware)
    # 2nd: Prometheus HTTP metrics collection
    app.add_middleware(PrometheusMiddleware)
    # 1.5th: collapse unexpected downstream errors into one clean JSON response
    app.add_middleware(UnhandledExceptionMiddleware)
    # 1st (outermost): handles OPTIONS preflight immediately
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Requested-With",
            "X-Request-ID",
            "X-API-Key",
            "X-Idempotency-Key",
            "X-Trace-ID",
            "X-CSRF-Token",
        ],
    )
