"""财务管理 API 路由"""

import logging
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/finance", tags=["Finance"])


class BudgetCreate(BaseModel):
    category: str
    amount: float
    period: str


class InvoiceCreate(BaseModel):
    invoice_number: str
    amount: float
    customer_id: str | None = None


@router.get("/budgets")
async def list_budgets(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取预算列表"""
    try:
        org_id = getattr(req.state, "org_id", None)
        db = getattr(req.state, "db", None)

        # 确保遗漏的更新逻辑也同步为 organization_id
        await db.execute(
            "UPDATE finance_budgets SET current = $1 WHERE id = $2 AND organization_id = $3",
            new_amount, budget_id, user["org_id"]
        )
        query = db.table("finance_budgets").select("*")
        if org_id:
            query = query.eq("organization_id", org_id)

        result = await query.execute()
        return api_success(data={"budgets": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list budgets: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取预算失败")


@router.post("/budgets")
async def create_budget(
    body: BudgetCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建预算"""
    try:
        org_id = getattr(req.state, "org_id", None)
        db = getattr(req.state, "db", None)

        data = body.model_dump()
        data["organization_id"] = org_id
        data["created_by"] = user_id

        result = await db.table("finance_budgets").insert(data).execute()
        return api_success(data={"budget": result.data[0] if result.data else None}, message="预算创建成功")
    except Exception as e:
        logger.error(f"Failed to create budget: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "创建预算失败")


@router.put("/budgets/{budget_id}")
async def update_budget(
    budget_id: str,
    body: BudgetCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新预算"""
    try:
        db = getattr(req.state, "db", None)
        data = body.model_dump(exclude_none=True)

        result = await db.table("finance_budgets").update(data).eq("id", budget_id).execute()
        return api_success(data={"budget": result.data[0] if result.data else None}, message="预算已更新")
    except Exception as e:
        logger.error(f"Failed to update budget: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "更新预算失败")


@router.post("/invoices")
async def create_invoice(
    body: InvoiceCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建发票"""
    try:
        org_id = getattr(req.state, "org_id", None)
        db = getattr(req.state, "db", None)

        data = body.model_dump()
        data["organization_id"] = org_id
        data["created_by"] = user_id

        result = await db.table("finance_invoices").insert(data).execute()
        return api_success(data={"invoice": result.data[0] if result.data else None}, message="发票创建成功")
    except Exception as e:
        logger.error(f"Failed to create invoice: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "创建发票失败")
