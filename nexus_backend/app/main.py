from fastapi import FastAPI, Response
from app.routers import performance, incentive, approval, kingdee, chat, documents, projects
import uvicorn
import os

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Project Nexus Backend",
    description="AI-Driven Low-Code Backend for Sales Performance & Governance",
    version="1.0.0"
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(performance.router)
app.include_router(incentive.router)
app.include_router(approval.router)
app.include_router(kingdee.router)
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(projects.router)

@app.get("/")
async def root():
    return {"message": "Project Nexus Backend is Running", "docs": "/docs"}

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
