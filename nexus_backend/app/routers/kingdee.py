from fastapi import APIRouter, Depends

from app.core.auth import get_current_user_id

router = APIRouter(prefix="/api/kingdee", tags=["Kingdee Mock"])


@router.get("/inventory/{item_id}")
async def get_inventory(item_id: str, user_id: str = Depends(get_current_user_id)):
    """金蝶 ERP 库存查询 — 暂未对接"""
    return {"success": False, "error": {"code": "SERVICE_UNAVAILABLE", "message": "金蝶 ERP 集成暂未开通，该功能需要配置金蝶 K3 Cloud SDK"}}


@router.post("/sync/salary")
async def sync_salary(user_id: str = Depends(get_current_user_id)):
    """金蝶薪资同步 — 暂未对接"""
    return {"success": False, "error": {"code": "SERVICE_UNAVAILABLE", "message": "金蝶薪资同步暂未开通，该功能需要配置金蝶 K3 Cloud SDK"}}
