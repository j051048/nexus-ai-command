from fastapi import FastAPI, Response
from app.routers import performance, incentive, approval, kingdee, chat, documents, projects, usage, organization
import uvicorn
import os

from fastapi.middleware.cors import CORSMiddleware
from app.core.rate_limiter import RateLimitMiddleware

app = FastAPI(
    title="Project Nexus Backend",
    description="AI-Driven Low-Code Backend for Sales Performance & Governance",
    version="1.0.0"
)

# P2: Event Bus lifecycle management
from app.services.event_bus import event_bus
from app.services.cache_service import cache_service
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events"""
    # Startup
    print("🚀 Starting Nexus Backend...")
    await cache_service.init()
    await event_bus.start()
    print("✅ Event Bus started")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down Nexus Backend...")
    await event_bus.stop()
    from app.services.audit_logger import audit_logger
    await audit_logger.force_flush()
    print("✅ Cleanup complete")

# Re-create app with lifespan
app = FastAPI(
    title="Project Nexus Backend",
    description="AI-Driven Low-Code Backend for Sales Performance & Governance",
    version="1.0.0",
    lifespan=lifespan
)

# Sentry Initialization
import sentry_sdk
from app.core.config import settings

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        traces_sample_rate=1.0,
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of sampled transactions.
        profiles_sample_rate=1.0,
    )
    print("✅ Sentry Initialized")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

# CORS Configuration
from app.core.config import settings

# CORS Configuration
origins = settings.CORS_ORIGINS

@app.get("/api/test-ai")
async def test_ai_connectivity():
    """Test connectivity from Backend to AI Gateway"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try to reach the proxy root or a public endpoint
            resp = await client.get("https://proxy.flydao.top")
            return {
                "status": "ok", 
                "gateway_response_code": resp.status_code, 
                "message": "Successfully reached AI Gateway"
            }
    except Exception as e:
        return {"status": "error", "detail": str(e)}

# P0 Security Fix: Restrict CORS to whitelist
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# P0 Security Fix: Rate limiting middleware
app.add_middleware(RateLimitMiddleware)

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

@app.get("/")
async def root():
    return {"message": "Project Nexus Backend is Running", "docs": "/docs"}

@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring"""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENV
    }

@app.get("/api/dashboard/boss")
async def boss_dashboard():
    """
    Lightweight endpoint for Boss. 
    Fetches real data from Supabase.
    """
    from app.core.database import supabase
    
    if not supabase:
        return {
            "error": "Database connection unavailable",
            "pending_approvals": 0,
            "abnormal_expenses": [],
            "top_performers": [],
            "system_status": "Database Error"
        }

    try:
        # 1. Get Pending Approvals Count
        pending_res = await supabase.table("approval_requests")\
            .select("count", count="exact")\
            .eq("status", "pending")\
            .execute()
        pending_count = pending_res.count if pending_res.count is not None else 0

        # 2. Get Abnormal Expenses (High amount pending expenses)
        # Using a simple threshold for now, e.g. > 1000
        abnormal_res = await supabase.table("approval_requests")\
            .select("id, description, amount, users:submitted_by(name)")\
            .eq("status", "pending")\
            .eq("type", "expense")\
            .gt("amount", 1000)\
            .order("amount", desc=True)\
            .limit(5)\
            .execute()
            
        abnormal_expenses = []
        for item in abnormal_res.data:
            user_name = "Unknown"
            if item.get("users"):
                user_name = item["users"].get("name", "Unknown")
            
            abnormal_expenses.append({
                "id": item["id"],
                "user": user_name,
                "amount": item["amount"],
                "reason": item.get("description", "No description")
            })

        # 3. Get Top Performers
        users_res = await supabase.table("users")\
            .select("name, score, total_bonus")\
            .order("score", desc=True)\
            .limit(3)\
            .execute()
            
        top_performers = [u["name"] for u in users_res.data]

        return {
            "pending_approvals": pending_count,
            "abnormal_expenses": abnormal_expenses,
            "top_performers": top_performers,
            "system_status": "Healthy"
        }

    except Exception as e:
        print(f"Error fetching boss dashboard data: {e}")
        return {
            "pending_approvals": 0, 
            "abnormal_expenses": [],
            "top_performers": [],
            "system_status": f"Error: {str(e)}"
        }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
