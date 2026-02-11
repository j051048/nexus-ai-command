from fastapi import APIRouter
from app.models.schemas import KingdeeSyncRequest
import random

router = APIRouter(prefix="/api/kingdee", tags=["Kingdee Mock"])


@router.get("/inventory/{item_id}")
async def get_inventory(item_id: str):
    """Mock reading inventory from Kingdee ERP"""
    return {
        "item_id": item_id,
        "stock_count": random.randint(10, 5000),
        "warehouse": "Shenzhen_HQ",
    }


@router.post("/sync/salary")
async def sync_salary(request: KingdeeSyncRequest):
    """Mock syncing bonus data TO Kingdee Salary Module"""
    return {
        "status": "success",
        "synced_records": 15,
        "total_amount": 45000.00,
        "message": "Synced to Kingdee K3 Cloud successfully",
    }
