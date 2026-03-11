import os
import warnings
from contextlib import asynccontextmanager, suppress

# 过滤第三方依赖的已知弃用警告（不影响功能）
warnings.filterwarnings(
    "ignore",
    message="ARC4 has been moved",
    category=DeprecationWarning,
)

import sentry_sdk
import uvicorn
from fastapi import Depends, FastAPI, Response
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
from app.core.exception_handlers import register_exception_handlers
from app.routers import (
    api_docs,
    api_keys,
    approval,
    audio,
    backups,
    billing,
    chat,
    compliance,
    competitors,
    contracts,
    crm,
    dashboard,
    data_transfer,
    documents,
    form_schemas,
    im_callbacks,
    im_chat,
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
from app.routers import assets as assets_router
from app.routers import org_structure as org_structure_router
from app.routers import system_configs as system_configs_router
from app.routers import work_orders as work_orders_router
from app.routers import mcp as mcp_router
from app.routers import robot as robot_router
from app.routers import ws as ws_router
from app.routers import scheduled_tasks as scheduled_tasks_router
from app.routers import attendance as attendance_router
from app.routers import expenses as expenses_router
from app.routers import inventory as inventory_router
from app.routers import certificates as certificates_router
from app.routers import approval_flows as approval_flows_router

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
    from app.routers import admin_rag
except ImportError:
    admin_rag = None
try:
    from app.routers import ai_feedback
except ImportError:
    ai_feedback = None
from app.services.audit_logger import audit_logger
from app.services.cache_service import cache_service
from app.services.event_bus import event_bus
import app.services.enterprise_event_handlers  # noqa: F401 — registers @on() handlers

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

    # #20: 启动时验证关键表列是否存在
    from app.core.schema_validator import validate_schema

    try:
        schema_warnings = await validate_schema()
        if schema_warnings:
            logger.warning(f"Schema validation: {len(schema_warnings)} warnings")
    except Exception as e:
        logger.warning(f"Schema validation skipped: {e}")

    # #18: 自动执行数据库迁移（需要 AUTO_MIGRATE=true）
    from app.core.migration_runner import run_migrations

    try:
        applied = await run_migrations()
        if applied:
            logger.info(f"Migration runner: {len(applied)} migrations processed")
    except Exception as e:
        logger.warning(f"Migration runner skipped: {e}")

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

# Register global exception handlers (validation, HTTP, and generic 500)
register_exception_handlers(app)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


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
#   CORS -> RateLimit -> SecurityHeaders -> RequestID -> DataMasking -> CSRF -> APIKey -> Idempotency -> TenantContext
#
# CORS MUST be outermost so browser preflight (OPTIONS) is handled immediately
# before any auth/rate-limit middleware rejects the request.
app.add_middleware(TenantContextMiddleware)  # 9th: innermost, sets up tenant DB scope
from app.core.idempotency_middleware import IdempotencyMiddleware  # noqa: E402

app.add_middleware(IdempotencyMiddleware)  # 8th: idempotency dedup for write operations
from app.core.api_key_middleware import APIKeyMiddleware  # noqa: E402

app.add_middleware(APIKeyMiddleware)  # 7th: API Key auth sets org_id before tenant context
from app.core.csrf_middleware import CSRFMiddleware  # noqa: E402

app.add_middleware(CSRFMiddleware)  # 6th: CSRF protection for cookie-based auth
from app.core.data_masking import DataMaskingMiddleware  # noqa: E402

app.add_middleware(DataMaskingMiddleware)  # 5th: auto-mask sensitive fields in responses
app.add_middleware(RequestIDMiddleware)  # 4th: adds request tracing ID + sets contextvars
app.add_middleware(SecurityHeadersMiddleware)  # 3rd: security response headers
app.add_middleware(RateLimitMiddleware)  # 2nd: blocks abuse BEFORE DB queries
app.add_middleware(
    CORSMiddleware,  # 1st: outermost — handles OPTIONS preflight immediately
    allow_origins=origins,
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


# Include Routers
app.include_router(performance.router)
app.include_router(incentive.router)
app.include_router(approval.router)
app.include_router(kingdee.router)
app.include_router(chat.router)
app.include_router(audio.router)
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
app.include_router(im_chat.router)
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
app.include_router(competitors.router)
app.include_router(super_admin.router)
app.include_router(crm.router)
app.include_router(api_docs.router)
app.include_router(backups.router)
app.include_router(api_keys.router)
app.include_router(onboarding.router)
app.include_router(ws_router.router)
app.include_router(scheduled_tasks_router.router)
app.include_router(dashboard.router)
app.include_router(system_configs_router.router)
app.include_router(org_structure_router.router)
app.include_router(assets_router.router)
app.include_router(work_orders_router.router)
app.include_router(attendance_router.router)
app.include_router(expenses_router.router)
app.include_router(inventory_router.router)
app.include_router(certificates_router.router)
app.include_router(approval_flows_router.router)

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
if admin_rag:
    app.include_router(admin_rag.router)
if ai_feedback:
    app.include_router(ai_feedback.router)


@app.get("/")
async def root():
    return {"message": "Project Nexus Backend is Running", "docs": "/docs"}


# Health check cache: avoid thundering herd on /health under load balancer polling
_health_cache: dict = {"result": None, "expires": 0.0}
_HEALTH_CACHE_TTL = 5.0  # seconds


@app.get("/health")
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.

    Cached for 5 seconds to prevent connection pool exhaustion under
    high-frequency polling (load balancer, k8s liveness probe, monitoring).
    Each downstream check has an independent 2s timeout to avoid cascade.
    """
    import asyncio
    import time

    # Return cached result if still fresh
    now = time.monotonic()
    if _health_cache["result"] and now < _health_cache["expires"]:
        return _health_cache["result"]

    import httpx

    from app.core.config import settings
    from app.core.database import supabase
    from app.services.cache_service import cache_service

    async def check_db() -> str:
        try:
            if not supabase:
                return "not_configured"
            await asyncio.wait_for(
                supabase.table("users").select("count", count="exact").limit(1).execute(),
                timeout=2.0,
            )
            return "connected"
        except Exception as e:
            logger.warning(f"Health check DB error: {e}")
            return "error" if settings.IS_PRODUCTION else f"error: {str(e)[:50]}"

    async def check_cache() -> str:
        try:
            ok = await asyncio.wait_for(cache_service.ping(), timeout=2.0)
            return "connected" if ok else "error"
        except Exception as e:
            return "error" if settings.IS_PRODUCTION else f"error: {str(e)[:50]}"

    async def check_ai() -> str:
        try:
            base_url = settings.AI_BASE_URL or "https://api.openai.com/v1"
            domain = base_url.split("/v1")[0].split("/chat")[0]
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(domain)
                return f"reachable ({resp.status_code})"
        except Exception as e:
            return "unreachable" if settings.IS_PRODUCTION else f"unreachable: {str(e)[:50]}"

    async def check_llm_gateway() -> str:
        try:
            if not supabase:
                return "not_configured"
            model_res = await asyncio.wait_for(
                supabase.table("llm_model_config")
                .select("id", count="exact")
                .eq("status", "enabled")
                .eq("is_deleted", False)
                .execute(),
                timeout=2.0,
            )
            enabled_count = model_res.count if model_res.count is not None else len(model_res.data or [])
            return f"ok ({enabled_count} models)" if enabled_count > 0 else "no_models_enabled"
        except Exception:
            return "available"

    # Run all checks concurrently with individual timeouts
    db_status, cache_status, ai_status, llm_gateway_status = await asyncio.gather(
        check_db(), check_cache(), check_ai(), check_llm_gateway()
    )

    is_healthy = db_status == "connected" and cache_status == "connected"
    status_code = 200 if is_healthy else 503

    response = UTF8JSONResponse(
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

    # Cache the result
    _health_cache["result"] = response
    _health_cache["expires"] = now + _HEALTH_CACHE_TTL

    return response


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
