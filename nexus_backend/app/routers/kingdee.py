from fastapi import APIRouter, Depends
from app.models.schemas import KingdeeSyncRequest
from app.core.auth import get_current_user_id
import random

router = APIRouter(prefix="/api/kingdee", tags=["Kingdee Mock"])

_DEV_WARNING = (
    "This is a MOCK endpoint. No real Kingdee ERP connection is established. "
    "Replace with actual Kingdee K3 Cloud SDK integration before production use."
)


@router.get("/inventory/{item_id}")
async def get_inventory(item_id: str, user_id: str = Depends(get_current_user_id)):
    """Mock reading inventory from Kingdee ERP"""
    return {
        "item_id": item_id,
        "stock_count": random.randint(10, 5000),
        "warehouse": "Shenzhen_HQ",
        "_is_mock": True,
        "_dev_warning": _DEV_WARNING,
    }


@router.post("/sync/salary")
async def sync_salary(
    request: KingdeeSyncRequest, user_id: str = Depends(get_current_user_id)
):
    """Mock syncing bonus data TO Kingdee Salary Module"""
    return {
        "status": "success",
        "synced_records": 15,
        "total_amount": 45000.00,
        "message": "Synced to Kingdee K3 Cloud successfully",
        "_is_mock": True,
        "_dev_warning": _DEV_WARNING,
    }
