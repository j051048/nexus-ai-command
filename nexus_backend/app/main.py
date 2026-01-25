from fastapi import FastAPI
from app.routers import performance, incentive, approval, kingdee
import uvicorn
import os

app = FastAPI(
    title="Project Nexus Backend",
    description="AI-Driven Low-Code Backend for Sales Performance & Governance",
    version="1.0.0"
)

# Include Routers
app.include_router(performance.router)
app.include_router(incentive.router)
app.include_router(approval.router)
app.include_router(kingdee.router)

@app.get("/")
async def root():
    return {"message": "Project Nexus Backend is Running", "docs": "/docs"}

@app.get("/api/dashboard/boss")
async def boss_dashboard():
    """
    Lightweight endpoint for Boss. 
    Only shows exceptions and high-level KPIs.
    """
    return {
        "pending_approvals": 2, # Mock count
        "abnormal_expenses": [
            {"id": "inv_999", "user": "Sales_A", "amount": 25000, "reason": "Expensive client dinner"}
        ],
        "top_performers": ["Alice", "Bob"],
        "system_status": "Healthy"
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
