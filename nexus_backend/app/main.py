import os
import warnings

# 过滤第三方依赖的已知弃用警告（不影响功能）
warnings.filterwarnings(
    "ignore",
    message="ARC4 has been moved",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message="Core Pydantic V1 functionality isn't compatible with Python 3.14",
    category=UserWarning,
)

import sentry_sdk
import uvicorn
from fastapi import Depends, FastAPI, Request, Response

from app.core.auth import get_current_user_id
from app.core.config import settings
from app.core.logging_config import get_logger, setup_logging
from app.core.metrics import generate_metrics_text
from app.core.responses import UTF8JSONResponse
from app.core.exception_handlers import register_exception_handlers
from app.startup import lifespan, register_middleware, register_routers

# P2 Enhancement: Initialize structured logging FIRST
setup_logging()
logger = get_logger(__name__)

# Sentry Initialization (Item 26: security endpoints get 100% sampling)
if settings.SENTRY_DSN:
    _security_paths = (
        "/api/auth/",
        "/api/approval/",
        "/api/billing/",
        "/api/payments/",
        "/api/permissions/",
    )

    def _sentry_traces_sampler(sampling_context):
        """100% sampling for security-critical endpoints, 10% for the rest."""
        try:
            path = sampling_context.get("asgi_scope", {}).get("path", "")
            if any(path.startswith(p) for p in _security_paths):
                return settings.SENTRY_SECURITY_SAMPLE_RATE  # default 1.0
        except Exception as e:
            logger.debug("Sentry traces sampler error (fallback to 0.1): %s", e)
        return 0.1

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sampler=_sentry_traces_sampler,
        profiles_sample_rate=0.1,
    )
    logger.info("Sentry initialized (security endpoints: 100% sampling)")

# Ensure enterprise event handlers are registered at import time
import app.services.enterprise_event_handlers  # noqa: F401


def create_app() -> FastAPI:
    """Application factory — assembles FastAPI app with middleware, routers, and routes."""

    application = FastAPI(
        title="Project Nexus Backend",
        default_response_class=UTF8JSONResponse,
        description=(
            "AI-Driven Low-Code Backend for Sales Performance & Governance.\n\n"
            "## Core Capabilities\n"
            "- **AI Chat**: LangGraph-powered agentic chat with tool calling\n"
            "- **Knowledge Base**: RAG with hybrid search (vector + keyword + reranking)\n"
            "- **Approval System**: Multi-level approval workflows with AI escalation\n"
            "- **Sales Pipeline**: CRM with gamification and performance tracking\n"
            "- **MCP Server**: Model Context Protocol tool exposure for AI interop\n"
            "- **Multi-tenant**: Row Level Security with per-org credit quotas\n\n"
            "## Authentication\n"
            "All endpoints (except `/health`, `/docs`) require a Bearer JWT token "
            "obtained via Supabase Auth."
        ),
        version="2.0.0",
        lifespan=lifespan,
        openapi_tags=[
            {"name": "Chat", "description": "AI chat and conversation management"},
            {
                "name": "Documents",
                "description": "Document upload, RAG, and knowledge base",
            },
            {
                "name": "Billing",
                "description": "Subscription plans, trials, and payments",
            },
            {
                "name": "MCP Server",
                "description": "Model Context Protocol tool registry",
            },
            {
                "name": "Robot/RPA",
                "description": "Robot and RPA device command interface (stub)",
            },
            {
                "name": "Kingdee",
                "description": "Kingdee ERP integration through a configured HTTP gateway",
            },
            {"name": "Webhooks", "description": "Webhook subscription and delivery"},
            {"name": "OAuth", "description": "OAuth 2.0 authorization server"},
            {
                "name": "IM OAuth",
                "description": "IM platform (WeChat Work/DingTalk/Feishu) OAuth SSO",
            },
            {
                "name": "IM Callbacks",
                "description": "IM platform interactive card callback handlers",
            },
            {
                "name": "IM Settings",
                "description": "IM platform integration configuration management",
            },
        ],
    )

    # OpenTelemetry distributed tracing
    from app.core.telemetry import setup_telemetry

    setup_telemetry(application)

    # Global exception handlers (validation, HTTP, and generic 500)
    register_exception_handlers(application)

    # Middleware (order-sensitive)
    register_middleware(application)

    # All routers
    register_routers(application)

    # --- Inline routes ---

    @application.get("/")
    async def root():
        return {"message": "Project Nexus Backend is Running", "docs": "/docs"}

    @application.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return Response(status_code=204)

    @application.get("/api/ping")
    async def api_ping():
        """Diagnostic endpoint to verify root /api connectivity."""
        return {"status": "ok", "message": "API is reachable"}

    @application.get("/metrics", include_in_schema=False)
    async def prometheus_metrics(request: Request):
        """Prometheus-compatible metrics endpoint. Requires X-Health-Token header."""

        expected_token = os.getenv("HEALTH_CHECK_TOKEN", "")
        provided_token = request.headers.get("X-Health-Token", "")
        if not expected_token and settings.IS_PRODUCTION:
            return UTF8JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "detail": "HEALTH_CHECK_TOKEN not configured",
                },
            )
        if expected_token and provided_token != expected_token:
            return UTF8JSONResponse(status_code=403, content={"error": "Forbidden"})

        return Response(
            content=generate_metrics_text(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @application.get("/api/test-ai")
    async def test_ai_connectivity(user_id: str = Depends(get_current_user_id)):
        """Test connectivity from Backend to AI Gateway (dev/test only)"""
        if settings.ENV not in ("dev", "development", "test"):
            return {
                "status": "error",
                "detail": "This endpoint is only available in dev/test environments",
            }
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    settings.AI_BASE_URL or "https://api.openai.com/v1"
                )
                return {
                    "status": "ok",
                    "gateway_response_code": resp.status_code,
                    "message": "Successfully reached AI Gateway",
                }
        except Exception:
            return {"status": "error", "detail": "Gateway unreachable"}

    # G6: Health check — O(1) cached return via background refresh
    @application.get("/health/live")
    async def health_live():
        """Kubernetes liveness probe: process is alive, no downstream I/O."""
        return UTF8JSONResponse(
            status_code=200,
            content={
                "status": "alive",
                "version": settings.VERSION,
                "environment": settings.ENV,
            },
        )

    @application.get("/health/ready")
    async def health_ready():
        """Kubernetes readiness probe: cached dependency readiness, O(1)."""
        from app.core.health_cache import health_cache

        cached = health_cache.get_cached_health()
        checks = cached.get("checks", {})
        ready = cached.get("status") == "healthy"
        ready = ready and checks.get("database") == "connected"
        ready = ready and checks.get("cache") == "connected"
        return UTF8JSONResponse(
            status_code=200 if ready else 503,
            content={
                "status": "ready" if ready else "not_ready",
                "version": settings.VERSION,
                "environment": settings.ENV,
                "checks": checks,
            },
        )

    @application.get("/health")
    async def health_check():
        """
        Health check endpoint for load balancers and monitoring.

        Returns cached status from background health checker (O(1), no I/O).
        Background task refreshes every 10 seconds.
        """
        from app.core.health_cache import health_cache

        cached = health_cache.get_cached_health()
        http_status = cached.get("_http_status", 200)
        # Return without the internal _http_status field
        content = {k: v for k, v in cached.items() if k != "_http_status"}
        return UTF8JSONResponse(status_code=http_status, content=content)

    @application.get("/health/deep")
    async def health_deep(request: Request):
        """
        Deep health check — covers Redis, DB, LLM provider, and Celery broker.

        Requires X-Health-Token header matching HEALTH_CHECK_TOKEN env var.
        Use for readiness probes and operational dashboards.
        Not cached (each call does live checks).
        """
        import asyncio

        # Auth: require health check token
        expected_token = os.getenv("HEALTH_CHECK_TOKEN", "")
        provided_token = request.headers.get("X-Health-Token", "")
        if not expected_token and settings.IS_PRODUCTION:
            return UTF8JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "detail": "HEALTH_CHECK_TOKEN not configured",
                },
            )
        if expected_token and provided_token != expected_token:
            return UTF8JSONResponse(status_code=403, content={"error": "Forbidden"})

        from app.core.database import supabase
        from app.services.cache_service import cache_service

        checks = {}

        # 1. Database
        try:
            if not supabase:
                checks["database"] = {"status": "not_configured"}
            else:
                await asyncio.wait_for(
                    supabase.table("users")
                    .select("count", count="exact")
                    .limit(1)
                    .execute(),
                    timeout=3.0,
                )
                checks["database"] = {"status": "connected"}
        except Exception:
            checks["database"] = {"status": "unavailable"}

        # 2. Redis/Cache
        try:
            ok = await asyncio.wait_for(cache_service.ping(), timeout=3.0)
            checks["redis"] = {"status": "connected" if ok else "error"}
        except Exception:
            checks["redis"] = {"status": "unavailable"}

        # 3. LLM Provider (check API key is configured)
        llm_status = "not_configured"
        if settings.AI_API_KEY:
            llm_status = "configured"
            try:
                import httpx

                base_url = settings.AI_BASE_URL or "https://api.openai.com/v1"
                domain = base_url.split("/v1")[0].split("/chat")[0]
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(domain)
                    llm_status = f"reachable ({resp.status_code})"
            except Exception:
                llm_status = "configured_but_unreachable"
        checks["llm_provider"] = {"status": llm_status}

        # 4. Celery broker
        try:
            broker_url = os.getenv("CELERY_BROKER_URL")
            if broker_url:
                checks["celery_broker"] = {"status": "configured"}
            else:
                checks["celery_broker"] = {"status": "not_configured"}
        except Exception:
            checks["celery_broker"] = {"status": "unavailable"}

        # Overall status
        critical = [
            checks.get("database", {}).get("status"),
            checks.get("redis", {}).get("status"),
        ]
        if all(s == "connected" for s in critical):
            overall = "healthy"
        elif any(s == "error" for s in critical):
            overall = "unhealthy"
        else:
            overall = "degraded"

        # 5. Degradation registry — aggregated fallback tracking
        from app.core.degradation_registry import degradation_registry

        degradation_summary = degradation_registry.summary()
        checks["degradations"] = degradation_summary
        if degradation_summary["degraded"] and overall == "healthy":
            overall = "degraded"

        status_code = 200 if overall == "healthy" else 503
        return UTF8JSONResponse(
            status_code=status_code,
            content={
                "status": overall,
                "version": settings.VERSION,
                "environment": settings.ENV,
                "checks": checks,
            },
        )

    return application


# Module-level `app` for uvicorn (app.main:app)
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
