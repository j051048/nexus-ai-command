"""销售目标和指标 API 路由"""

import logging

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sales", tags=["Sales"])


class TargetCreate(BaseModel):
    title: str = Field(..., max_length=200)
    target_value: float
    period: str = Field(..., max_length=50)
    assigned_to: str | None = None


@router.get("/targets")
async def list_targets(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取销售目标"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        result = (
            await db.table("sales_targets")
            .select("*")
            .eq("organization_id", org_id)
            .execute()
        )
        return api_success(data={"targets": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list targets: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取目标失败")


@router.post("/targets")
async def create_target(
    body: TargetCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建销售目标"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        data = body.model_dump()
        data["organization_id"] = org_id
        data["created_by"] = user_id

        result = await db.table("sales_targets").insert(data).execute()
        return api_success(data={"target": result.data[0] if result.data else None})
    except Exception as e:
        logger.error(f"Failed to create target: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "创建目标失败")


@router.delete("/targets/{target_id}")
async def delete_target(
    target_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """删除销售目标"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        await db.table("sales_targets").delete().eq("id", target_id).eq(
            "organization_id", org_id
        ).execute()
        return api_success(data={"deleted": True})
    except Exception as e:
        logger.error(f"Failed to delete target: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "删除目标失败")


@router.get("/metrics")
async def list_metrics(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取销售指标"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        result = (
            await db.table("sales_metrics")
            .select("*")
            .eq("organization_id", org_id)
            .execute()
        )
        return api_success(data={"metrics": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list metrics: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取指标失败")


# ── Pydantic Models ─────────────────────────────────────────────────────


class MetricsUpsert(BaseModel):
    user_id: str
    date: str
    calls_made: int | None = None
    deals_closed: int | None = None
    revenue: float | None = None
    leads_generated: int | None = None


# ── 扩展端点 ────────────────────────────────────────────────────────────


@router.get("/metrics/range")
async def list_metrics_by_range(
    req: Request,
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    user_id_filter: str | None = Query(
        None, alias="user_id", description="可选用户ID过滤"
    ),
    user_id: str = Depends(get_current_user_id),
):
    """按日期范围查询销售指标"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        query = (
            db.table("sales_metrics")
            .select("*")
            .eq("organization_id", org_id)
            .gte("date", start_date)
            .lte("date", end_date)
        )
        if user_id_filter:
            query = query.eq("user_id", user_id_filter)

        result = await query.execute()
        return api_success(data={"metrics": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list metrics by range: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "按范围查询指标失败")


@router.get("/team-performance")
async def get_team_performance(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """团队业绩排行"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        # 查询团队成员 Top 10
        users_result = (
            await db.table("users")
            .select("id, name, score, total_bonus")
            .eq("organization_id", org_id)
            .order("score", desc=True)
            .limit(10)
            .execute()
        )
        members = users_result.data or []

        # 批量查询这些用户的指标
        user_ids = [m["id"] for m in members]
        metrics = []
        if user_ids:
            metrics_result = (
                await db.table("sales_metrics")
                .select("*")
                .eq("organization_id", org_id)
                .in_("user_id", user_ids)
                .execute()
            )
            metrics = metrics_result.data or []

        return api_success(data={"members": members, "metrics": metrics})
    except Exception as e:
        logger.error(f"Failed to get team performance: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取团队业绩失败")


@router.get("/leaderboard")
async def get_leaderboard(
    req: Request,
    limit: int = Query(10, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
):
    """排行榜"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        result = (
            await db.table("users")
            .select("id, name, score, total_bonus, rank")
            .eq("organization_id", org_id)
            .order("score", desc=True)
            .limit(limit)
            .execute()
        )
        return api_success(data={"leaderboard": result.data or []})
    except Exception as e:
        logger.error(f"Failed to get leaderboard: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取排行榜失败")


@router.post("/metrics")
async def upsert_metrics(
    body: MetricsUpsert,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """保存/upsert 销售指标"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        data = body.model_dump(exclude_none=True)
        data["organization_id"] = org_id

        result = (
            await db.table("sales_metrics")
            .upsert(data, on_conflict="user_id,date")
            .execute()
        )
        return api_success(data={"metric": result.data[0] if result.data else {}})
    except Exception as e:
        logger.error(f"Failed to upsert metrics: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "保存指标失败")
