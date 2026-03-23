"""合同生命周期管理 API 路由"""

import logging

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.dependencies import require_role
from app.core.errors import ErrorCode, api_error, api_success
from app.models.schemas import ContractCreate, ContractEventCreate, ContractUpdate
from app.services.contract_service import contract_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/contracts", tags=["Contracts"])


@router.get("")
async def list_contracts(
    req: Request,
    status: str = None,
    contract_type: str = None,
    search: str = None,
    skip: int = 0,
    limit: int = 50,
    user_id: str = Depends(get_current_user_id),
):
    """获取合同列表"""
    try:
        limit = min(limit, 200)
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        filters = {}
        if status:
            filters["status"] = status
        if contract_type:
            filters["contract_type"] = contract_type
        if search:
            filters["search"] = search
        contracts = await contract_service.list_contracts(org_id=org_id, filters=filters if filters else None, db=db, skip=skip, limit=limit)
        return api_success(data={"contracts": contracts})
    except Exception as e:
        logger.error(f"Failed to list contracts: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "合同操作失败")


@router.post("")
async def create_contract(
    body: ContractCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建合同"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        data = body.model_dump(exclude_none=True)
        data["created_by"] = user_id
        result = await contract_service.create_contract(org_id=org_id, data=data, db=db)
        return api_success(data={"contract": result}, message="合同创建成功")
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "合同参数校验失败")
    except Exception as e:
        logger.error(f"Failed to create contract: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "合同操作失败")


@router.get("/stats")
async def get_contract_stats(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取合同统计"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        stats = await contract_service.get_contract_stats(org_id=org_id, db=db)
        return api_success(data={"stats": stats})
    except Exception as e:
        logger.error(f"Failed to get contract stats: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "合同操作失败")


@router.get("/expiring")
async def get_expiring_contracts(
    req: Request,
    days: int = 30,
    user_id: str = Depends(get_current_user_id),
):
    """获取即将到期合同"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        contracts = await contract_service.get_expiring_contracts(org_id=org_id, days=days, db=db)
        return api_success(data={"contracts": contracts})
    except Exception as e:
        logger.error(f"Failed to get expiring contracts: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "合同操作失败")


@router.get("/{contract_id}")
async def get_contract(
    contract_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取合同详情"""
    db = getattr(req.state, "db", None)
    contract = await contract_service.get_contract(contract_id=contract_id, db=db)
    if not contract:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "合同不存在")
    return api_success(data={"contract": contract})


@router.put("/{contract_id}")
async def update_contract(
    contract_id: str,
    body: ContractUpdate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新合同"""
    try:
        db = getattr(req.state, "db", None)
        data = body.model_dump(exclude_none=True)
        result = await contract_service.update_contract(contract_id=contract_id, data=data, db=db)
        return api_success(data={"contract": result}, message="合同已更新")
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "合同参数校验失败")
    except Exception as e:
        logger.error(f"Failed to update contract: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "合同操作失败")


@router.get("/{contract_id}/events")
async def get_contract_events(
    contract_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取合同事件时间线"""
    try:
        db = getattr(req.state, "db", None)
        events = await contract_service.get_contract_events(contract_id=contract_id, db=db)
        return api_success(data={"events": events})
    except Exception as e:
        logger.error(f"Failed to get contract events: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "合同操作失败")


@router.post("/{contract_id}/events")
async def add_contract_event(
    contract_id: str,
    body: ContractEventCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """添加合同事件"""
    try:
        db = getattr(req.state, "db", None)
        event = await contract_service.add_contract_event(
            contract_id=contract_id,
            event_type=body.event_type,
            description=body.description,
            user_id=user_id,
            db=db,
        )
        return api_success(data={"event": event}, message="事件已添加")
    except Exception as e:
        logger.error(f"Failed to add contract event: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "合同操作失败")


@router.delete("/{contract_id}")
async def delete_contract(
    contract_id: str,
    req: Request,
    user_id: str = Depends(require_role(["admin", "founder", "boss"])),
):
    """删除合同（软删除 - 标记为 cancelled 状态）"""
    try:
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        # Verify contract exists
        existing = await db.table("contracts").select("id,status").eq("id", contract_id).maybe_single().execute()
        if not existing.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "合同不存在")

        # Soft delete: update status to cancelled
        await db.table("contracts").update({"status": "cancelled"}).eq("id", contract_id).execute()

        # Record deletion event
        await contract_service.add_contract_event(
            contract_id=contract_id,
            event_type="deleted",
            description="合同已被管理员删除（标记为已取消）",
            user_id=user_id,
            db=db,
        )

        return api_success(None, message="合同已删除")
    except Exception as e:
        logger.error(f"Failed to delete contract: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "合同操作失败")
