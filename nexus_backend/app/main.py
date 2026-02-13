from fastapi import FastAPI, Response, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import os
import sentry_sdk

from app.routers import (
    performance,
    incentive,
    approval,
    kingdee,
    chat,
    documents,
    projects,
    usage,
    organization,
    import_data,
    qa_pairs,
    webhooks,
    oauth,
    compliance,
    billing,
    profile,
)
from app.core.auth import get_current_user_id
from app.core.rate_limiter import RateLimitMiddleware
from app.core.security_middleware import (
    SecurityHeadersMiddleware,
    RequestIDMiddleware,
    TenantContextMiddleware,
)
from app.core.logging_config import setup_logging, get_logger
from app.core.config import settings
from app.services.event_bus import event_bus
from app.services.cache_service import cache_service
from app.services.audit_logger import audit_logger

# P2 Enhancement: Initialize structured logging FIRST
setup_logging()
logger = get_logger(__name__)

# Sentry Initialization
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.1,  # P1 Optimization: Don't sample 100% in production
        profiles_sample_rate=1.0,
    )
    logger.info("✅ Sentry Initialized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events"""
    import asyncio

    # Startup
    logger.info("Starting Nexus Backend...")
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

    # Start background tenant monitoring (every 5 minutes)
    async def _tenant_monitor_loop():
        from app.services.tenant_credit_service import tenant_credit_service
        from app.core.database import supabase
        while True:
            await asyncio.sleep(300)
            try:
                await tenant_credit_service.monitor_all_tenants(db=supabase)
            except Exception as e:
                logger.error(f"Tenant monitoring error: {e}")

    monitor_task = asyncio.create_task(_tenant_monitor_loop())

    yield

    # Shutdown
    logger.info("Shutting down Nexus Backend...")
    monitor_task.cancel()
    await event_bus.stop()
    await audit_logger.force_flush()
    try:
        await connection_pool_service.close()
    except Exception:
        pass
    logger.info("Cleanup complete")


app = FastAPI(
    title="Project Nexus Backend",
    description="AI-Driven Low-Code Backend for Sales Performance & Governance",
    version="1.0.0",
    lifespan=lifespan,
)

# OpenTelemetry distributed tracing setup
from app.core.telemetry import setup_telemetry
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

    return JSONResponse(
        status_code=exc.status_code, content={"success": False, "error": error_content}
    )


# CORS Configuration
origins = settings.all_cors_origins


@app.get("/api/test-ai")
async def test_ai_connectivity():
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


# P0 Security Fix: Restrict CORS to whitelist
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-Request-ID"],
)

# P0 Security Fix: Rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# P2 Security: Security headers, Request ID, and Tenant Context
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(TenantContextMiddleware)


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


@app.get("/")
async def root():
    return {"message": "Project Nexus Backend is Running", "docs": "/docs"}


@app.get("/health")
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.
    P2 Enhancement: Added database connectivity check.
    """
    from app.core.database import supabase
    from app.services.cache_service import cache_service
    from app.core.config import settings
    import httpx

    db_status = "unknown"
    cache_status = "unknown"
    ai_status = "unknown"

    # NOTE: Health check intentionally uses global service-key client (not RLS-scoped)
    # because it runs without user auth context and needs unrestricted DB access to verify connectivity.
    # 1. Database Check
    try:
        if supabase:
            # Quick check - just verify connection
            await supabase.table("users").select("count", count="exact").limit(
                1
            ).execute()
            db_status = "connected"
        else:
            db_status = "not_configured"
    except Exception as e:
        db_status = f"error: {str(e)[:50]}"
        logger.warning(f"Health check DB error: {e}")

    # 2. Redis/Cache Check
    try:
        if await cache_service.ping():
            cache_status = "connected"
        else:
            cache_status = "error"
    except Exception as e:
        cache_status = f"error: {str(e)[:50]}"

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
        ai_status = f"unreachable: {str(e)[:50]}"

    return {
        "status": (
            "healthy"
            if db_status == "connected" and cache_status == "connected"
            else "degraded"
        ),
        "version": settings.VERSION,
        "environment": settings.ENV,
        "checks": {
            "database": db_status,
            "cache": cache_status,
            "ai_gateway": ai_status,
        },
    }


@app.get("/api/dashboard/boss")
async def boss_dashboard(request: Request, user_id: str = Depends(get_current_user_id)):
    """
    P1 Security Fix #6: Boss dashboard now requires authentication AND boss role.
    P0 Multi-tenancy: Uses request.state.db for scoped access.
    """
    client = request.state.db
    from app.core.errors import api_success, api_error, ErrorCode

    if not client:
        raise api_error(
            ErrorCode.DB_CONNECTION_ERROR, "Database connection unavailable"
        )

    try:
        # P1 Security Fix #6: Verify user has boss role
        user_res = (
            await client.table("users")
            .select("role")
            .eq("id", user_id)
            .single()
            .execute()
        )

        if not user_res.data or user_res.data.get("role") != "boss":
            raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "仅领导可访问此仪表板")

        # 1. Get Pending Approvals Count
        pending_res = (
            await client.table("approval_requests")
            .select("count", count="exact")
            .eq("status", "pending")
            .execute()
        )
        pending_count = pending_res.count if pending_res.count is not None else 0

        # 2. Get Abnormal Expenses (High amount pending expenses)
        abnormal_res = (
            await client.table("approval_requests")
            .select("id, description, amount, users:submitted_by(name)")
            .eq("status", "pending")
            .eq("type", "expense")
            .gt("amount", 1000)
            .order("amount", desc=True)
            .limit(5)
            .execute()
        )

        abnormal_expenses = []
        for item in abnormal_res.data:
            user_name = "Unknown"
            if item.get("users"):
                user_name = item["users"].get("name", "Unknown")

            abnormal_expenses.append(
                {
                    "id": item["id"],
                    "user": user_name,
                    "amount": item["amount"],
                    "reason": item.get("description", "No description"),
                }
            )

        # 3. Get Top Performers
        users_res = (
            await client.table("users")
            .select("name, score, total_bonus")
            .order("score", desc=True)
            .limit(3)
            .execute()
        )

        top_performers = [u["name"] for u in users_res.data]

        return api_success(
            data={
                "pending_approvals": pending_count,
                "abnormal_expenses": abnormal_expenses,
                "top_performers": top_performers,
                "system_status": "Healthy",
            }
        )

    except HTTPException:
        raise  # Re-raise HTTP exceptions (already handled by global handler)
    except Exception as e:
        logger.error(f"Error fetching boss dashboard data: {e}")
        # Standardize even fallback errors
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)

