import os
from contextlib import asynccontextmanager, suppress

import sentry_sdk
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.auth import get_current_user_id
from app.core.config import settings
from app.core.logging_config import get_logger, setup_logging
from app.core.rate_limiter import RateLimitMiddleware
from app.core.responses import UTF8JSONResponse
from app.core.security_middleware import (
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
    TenantContextMiddleware,
)
from app.routers import (
    api_docs,
    api_keys,
    approval,
    backups,
    billing,
    chat,
    compliance,
    contracts,
    crm,
    dashboard,
    data_transfer,
    documents,
    form_schemas,
    im_callbacks,
    im_oauth,
    im_settings,
    import_data,
    incentive,
    kingdee,
    memories,
    notifications,
    oauth,
    onboarding,
    organization,
    payments,
    performance,
    permissions,
    plugins,
    profile,
    projects,
    push,
    qa_pairs,
    reports,
    super_admin,
    training,
    usage,
    webhooks,
    workflow_templates,
    workflows,
)
from app.routers import mcp as mcp_router
from app.routers import robot as robot_router
from app.routers import ws as ws_router

# VMD (Virtual Marketing Department) routers — import individually to avoid all-or-nothing failure
try:
    from app.routers import llm_models
except ImportError:
    llm_models = None
try:
    from app.routers import vmd_tasks
except ImportError:
    vmd_tasks = None
try:
    from app.routers import vmd_clues
except ImportError:
    vmd_clues = None
try:
    from app.routers import vmd_dashboard
except ImportError:
    vmd_dashboard = None
try:
    from app.routers import vmd_compliance as vmd_compliance_router
except ImportError:
    vmd_compliance_router = None
try:
    from app.routers import admin_traces
except ImportError:
    admin_traces = None
try:
    from app.routers import ai_feedback
except ImportError:
    ai_feedback = None
from app.services.audit_logger import audit_logger
from app.services.cache_service import cache_service
from app.services.event_bus import event_bus

# P2 Enhancement: Initialize structured logging FIRST
setup_logging()
logger = get_logger(__name__)

# Sentry Initialization
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.1,  # P1 Optimization: Don't sample 100% in production
        profiles_sample_rate=0.1,  # P0 Fix: Reduced from 1.0 to avoid production overhead
    )
    logger.info("✅ Sentry Initialized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events"""
    import asyncio

    # Startup
    logger.info("Starting Nexus Backend...")

    from app.core.env_config import env_config

    env_errors = env_config.validate_all()
    if env_errors:
        for err in env_errors:
            logger.warning(f"Env config: {err}")
    else:
        logger.info("Environment configuration validated")

    await cache_service.init()
    await event_bus.start()
    logger.info("Event Bus started")

    # Initialize LangGraph checkpointer (for state persistence)
    from app.agent.checkpointer import setup_checkpointer

    try:
        await setup_checkpointer()
        logger.info("LangGraph Checkpointer initialized")
    except Exception as e:
        logger.warning(f"Checkpointer initialization skipped: {e}")

    # Cold start optimization: Initialize connection pools
    from app.services.connection_pool_service import connection_pool_service

    try:
        await connection_pool_service.init_all()
        logger.info("Connection pools initialized")
    except Exception as e:
        logger.warning(f"Connection pool init skipped: {e}")

    # Warm up tiktoken encoders (prevents first-request latency)
    try:
        from app.services.token_service import token_counter

        token_counter.count_tokens("warmup", "gpt-4o")
        token_counter.count_tokens("warmup", "gpt-4o-mini")
        logger.info("Token encoders warmed up")
    except Exception as e:
        logger.warning(f"Tiktoken warmup skipped: {e}")

    # P0-2: Background tasks migrated to Celery Beat (see app/tasks/scheduler.py)
    # - monitor_tenants (every 5 min)
    # - check_approval_timeouts (every 5 min)
    # - sync_im_platforms (every hour)

    # Start auto-trigger service (3.2 主动监控)
    from app.services.auto_trigger_service import auto_trigger_service

    try:
        await auto_trigger_service.start()
        logger.info("Auto-trigger service started")
    except Exception as e:
        logger.warning(f"Auto-trigger service start skipped: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Nexus Backend...")
    with suppress(Exception):
        await auto_trigger_service.stop()
    await event_bus.stop()
    await audit_logger.force_flush()
    with suppress(Exception):
        await connection_pool_service.close()
    logger.info("Cleanup complete")


app = FastAPI(
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
        {"name": "Documents", "description": "Document upload, RAG, and knowledge base"},
        {"name": "Billing", "description": "Subscription plans, trials, and payments"},
        {"name": "MCP Server", "description": "Model Context Protocol tool registry"},
        {"name": "Robot/RPA", "description": "Robot and RPA device command interface (stub)"},
        {"name": "Kingdee Mock", "description": "Mock Kingdee ERP integration (dev only)"},
        {"name": "Webhooks", "description": "Webhook subscription and delivery"},
        {"name": "OAuth", "description": "OAuth 2.0 authorization server"},
        {"name": "IM OAuth", "description": "IM platform (WeChat Work/DingTalk/Feishu) OAuth SSO"},
        {"name": "IM Callbacks", "description": "IM platform interactive card callback handlers"},
        {"name": "IM Settings", "description": "IM platform integration configuration management"},
    ],
)

# OpenTelemetry distributed tracing setup
from app.core.telemetry import setup_telemetry  # noqa: E402

setup_telemetry(app)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


# Global Exception Handler for Standardized Error Responses
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Standardize HTTP exceptions to matching API response format.
    Wraps standard HTTPExceptions into {"success": False, "error": ...}
    """
    error_content = exc.detail

    # If detail is already a dict (from api_error), use it directly
    # If it's a string (standard raise HTTPException), wrap it
    if isinstance(error_content, str):
        error_content = {"code": "HTTP_ERROR", "message": error_content}

    return UTF8JSONResponse(status_code=exc.status_code, content={"success": False, "error": error_content})


# CORS Configuration
origins = settings.all_cors_origins


@app.get("/api/test-ai")
async def test_ai_connectivity(user_id: str = Depends(get_current_user_id)):
    """Test connectivity from Backend to AI Gateway"""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://proxy.flydao.top")
            return {
                "status": "ok",
                "gateway_response_code": resp.status_code,
                "message": "Successfully reached AI Gateway",
            }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# P0 Security Fix: Middleware order matters - last added runs first (outermost).
# Execution order (outermost -> innermost):
#   CORS -> RateLimit -> SecurityHeaders -> RequestID -> APIKey -> Idempotency -> TenantContext
#
# CORS MUST be outermost so browser preflight (OPTIONS) is handled immediately
# before any auth/rate-limit middleware rejects the request.
app.add_middleware(TenantContextMiddleware)  # 7th: innermost, sets up tenant DB scope
from app.core.idempotency_middleware import IdempotencyMiddleware  # noqa: E402

app.add_middleware(IdempotencyMiddleware)  # 6th: idempotency dedup for write operations
from app.core.api_key_middleware import APIKeyMiddleware  # noqa: E402

app.add_middleware(APIKeyMiddleware)  # 5th: API Key auth sets org_id before tenant context
app.add_middleware(RequestIDMiddleware)  # 4th: adds request tracing ID
app.add_middleware(SecurityHeadersMiddleware)  # 3rd: security response headers
app.add_middleware(RateLimitMiddleware)  # 2nd: blocks abuse BEFORE DB queries
app.add_middleware(
    CORSMiddleware,  # 1st: outermost — handles OPTIONS preflight immediately
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Requested-With",
        "X-Request-ID",
        "X-API-Key",
        "X-Idempotency-Key",
        "X-Trace-ID",
    ],
)


# Include Routers
app.include_router(performance.router)
app.include_router(incentive.router)
app.include_router(approval.router)
app.include_router(kingdee.router)
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(projects.router)
app.include_router(usage.router)
app.include_router(organization.router)
app.include_router(import_data.router)
app.include_router(qa_pairs.router)
app.include_router(webhooks.router)
app.include_router(oauth.router)
app.include_router(compliance.router)
app.include_router(billing.router)
app.include_router(profile.router)
app.include_router(mcp_router.router)
app.include_router(robot_router.router)
app.include_router(workflows.router)
app.include_router(form_schemas.router)
app.include_router(push.router)
app.include_router(im_oauth.router)
app.include_router(im_callbacks.router)
app.include_router(im_settings.router)
app.include_router(permissions.router)
app.include_router(workflow_templates.router)
app.include_router(memories.router)
app.include_router(reports.router)
app.include_router(notifications.router)
app.include_router(payments.router)
app.include_router(data_transfer.router)
app.include_router(plugins.router)
app.include_router(training.router)
app.include_router(contracts.router)
app.include_router(super_admin.router)
app.include_router(crm.router)
app.include_router(api_docs.router)
app.include_router(backups.router)
app.include_router(api_keys.router)
app.include_router(onboarding.router)
app.include_router(ws_router.router)
app.include_router(dashboard.router)

# VMD (Virtual Marketing Department) routers
if llm_models:
    app.include_router(llm_models.router)
if vmd_tasks:
    app.include_router(vmd_tasks.router)
if vmd_compliance_router:
    app.include_router(vmd_compliance_router.router)
if vmd_clues:
    app.include_router(vmd_clues.router)
if vmd_dashboard:
    app.include_router(vmd_dashboard.router)
if admin_traces:
    app.include_router(admin_traces.router)
if ai_feedback:
    app.include_router(ai_feedback.router)


@app.get("/")
async def root():
    return {"message": "Project Nexus Backend is Running", "docs": "/docs"}


@app.get("/health")
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.
    P2 Enhancement: Added database connectivity check.
    """
    import httpx

    from app.core.config import settings
    from app.core.database import supabase
    from app.services.cache_service import cache_service

    db_status = "unknown"
    cache_status = "unknown"
    ai_status = "unknown"

    # NOTE: Health check intentionally uses global service-key client (not RLS-scoped)
    # because it runs without user auth context and needs unrestricted DB access to verify connectivity.
    # 1. Database Check
    try:
        if supabase:
            # Quick check - just verify connection
            await supabase.table("users").select("count", count="exact").limit(1).execute()
            db_status = "connected"
        else:
            db_status = "not_configured"
    except Exception as e:
        db_status = "error" if settings.IS_PRODUCTION else f"error: {str(e)[:50]}"
        logger.warning(f"Health check DB error: {e}")

    # 2. Redis/Cache Check
    try:
        cache_status = "connected" if await cache_service.ping() else "error"
    except Exception as e:
        cache_status = "error" if settings.IS_PRODUCTION else f"error: {str(e)[:50]}"

    # 3. AI Connectivity Check
    try:
        base_url = settings.AI_BASE_URL or "https://api.openai.com/v1"
        # Extract domain for ping
        domain = base_url.split("/v1")[0].split("/chat")[0]
        async with httpx.AsyncClient(timeout=2.0) as client:
            # Simple GET request to root or health of AI provider
            resp = await client.get(domain)
            ai_status = f"reachable ({resp.status_code})"
    except Exception as e:
        ai_status = "unreachable" if settings.IS_PRODUCTION else f"unreachable: {str(e)[:50]}"

    # 4. LLM Model Gateway Check (VMD)
    llm_gateway_status = "not_configured"
    try:
        if supabase:
            model_res = (
                await supabase.table("llm_model_config")
                .select("count", count="exact")
                .eq("status", "enabled")
                .eq("is_deleted", False)
                .execute()
            )
            enabled_count = model_res.count if model_res.count is not None else 0
            llm_gateway_status = f"ok ({enabled_count} models)" if enabled_count > 0 else "no_models_enabled"
    except Exception:
        llm_gateway_status = "available"  # Table may not exist yet, that's ok

    is_healthy = db_status == "connected" and cache_status == "connected"
    status_code = 200 if is_healthy else 503

    return UTF8JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if is_healthy else "degraded",
            "version": settings.VERSION,
            "environment": settings.ENV,
            "checks": {
                "database": db_status,
                "cache": cache_status,
                "ai_gateway": ai_status,
                "llm_model_gateway": llm_gateway_status,
            },
        },
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
