from fastapi import APIRouter

router = APIRouter(prefix="/api/kingdee", tags=["Kingdee"])


@router.get("/inventory/{item_id}")
async def get_inventory(item_id: str):
    """金蝶 ERP 库存查询 — 暂未对接"""
    return {"success": False, "error": {"code": "SERVICE_UNAVAILABLE", "message": "金蝶 ERP 集成暂未开通，该功能需要配置金蝶 K3 Cloud SDK"}}


@router.post("/sync/salary")
async def sync_salary():
    """金蝶薪资同步 — 暂未对接"""
    return {"success": False, "error": {"code": "SERVICE_UNAVAILABLE", "message": "金蝶薪资同步暂未开通，该功能需要配置金蝶 K3 Cloud SDK"}}
