"""Usage statistics, cost reporting, and model ranking endpoints."""

import logging

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

from ._shared import _get_admin_client

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/usage/stats")
async def get_usage_stats(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    start_date: str | None = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="结束日期 (YYYY-MM-DD)"),
    model_code: str | None = Query(None, description="模型编码"),
    scene_code: str | None = Query(None, description="场景编码"),
    agent_code: str | None = Query(None, description="Agent编码"),
    group_by: str = Query("day", description="分组维度: model/scene/agent/user/day"),
):
    """多维度用量统计"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        client = _get_admin_client()

        query = client.table("llm_call_log").select("*").eq("tenant_id", org_id)
        if start_date:
            query = query.gte("create_time", f"{start_date}T00:00:00")
        if end_date:
            query = query.lte("create_time", f"{end_date}T23:59:59")
        if model_code:
            query = query.eq("model_code", model_code)
        if scene_code:
            query = query.eq("scene_code", scene_code)
        if agent_code:
            query = query.eq("agent_code", agent_code)

        res = await query.order("create_time", desc=True).execute()
        logs = res.data or []

        # Aggregate by group_by dimension
        stats: dict = {}
        for log in logs:
            if group_by == "model":
                key = log.get("model_code", "unknown")
            elif group_by == "scene":
                key = log.get("scene_code", "unknown")
            elif group_by == "agent":
                key = log.get("agent_code", "unknown")
            elif group_by == "user":
                key = log.get("user_id", "unknown")
            else:  # day
                key = str(log.get("create_time", ""))[:10]

            if key not in stats:
                stats[key] = {
                    "group": key,
                    "total_calls": 0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cost": 0.0,
                    "success_count": 0,
                    "error_count": 0,
                }
            stats[key]["total_calls"] += 1
            stats[key]["total_input_tokens"] += log.get("input_tokens", 0) or 0
            stats[key]["total_output_tokens"] += log.get("output_tokens", 0) or 0
            stats[key]["total_cost"] += float(log.get("call_cost", 0) or 0)
            if log.get("status") == "success":
                stats[key]["success_count"] += 1
            else:
                stats[key]["error_count"] += 1

        return api_success(
            data={
                "group_by": group_by,
                "stats": list(stats.values()),
                "total_records": len(logs),
            }
        )
    except Exception as e:
        logger.error(f"Usage stats error: user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "用量查询失败")


@router.get("/usage/cost-report")
async def get_cost_report(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    start_date: str | None = Query(None, description="开始日期"),
    end_date: str | None = Query(None, description="结束日期"),
):
    """成本报告（含分类明细）"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        client = _get_admin_client()

        query = client.table("llm_call_log").select("*").eq("tenant_id", org_id)
        if start_date:
            query = query.gte("create_time", f"{start_date}T00:00:00")
        if end_date:
            query = query.lte("create_time", f"{end_date}T23:59:59")

        res = await query.execute()
        logs = res.data or []

        total_cost = 0.0
        by_model: dict = {}
        by_scene: dict = {}
        for log in logs:
            cost = float(log.get("call_cost", 0) or 0)
            total_cost += cost

            model = log.get("model_code", "unknown")
            by_model[model] = by_model.get(model, 0.0) + cost

            scene = log.get("scene_code", "unknown")
            by_scene[scene] = by_scene.get(scene, 0.0) + cost

        return api_success(
            data={
                "total_cost": round(total_cost, 4),
                "total_calls": len(logs),
                "by_model": [
                    {"model": k, "cost": round(v, 4)} for k, v in sorted(by_model.items(), key=lambda x: -x[1])
                ],
                "by_scene": [
                    {"scene": k, "cost": round(v, 4)} for k, v in sorted(by_scene.items(), key=lambda x: -x[1])
                ],
            }
        )
    except Exception as e:
        logger.error(f"Cost report error: user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "用量查询失败")


@router.get("/usage/model-ranking")
async def get_model_ranking(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50, description="排名数量"),
):
    """模型使用排行"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        client = _get_admin_client()

        query = client.table("llm_call_log").select("*").eq("tenant_id", org_id)
        if start_date:
            query = query.gte("create_time", f"{start_date}T00:00:00")
        if end_date:
            query = query.lte("create_time", f"{end_date}T23:59:59")

        res = await query.execute()
        logs = res.data or []

        ranking: dict = {}
        for log in logs:
            model = log.get("model_code", "unknown")
            if model not in ranking:
                ranking[model] = {
                    "model_code": model,
                    "call_count": 0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                }
            ranking[model]["call_count"] += 1
            ranking[model]["total_tokens"] += (log.get("input_tokens", 0) or 0) + (log.get("output_tokens", 0) or 0)
            ranking[model]["total_cost"] += float(log.get("call_cost", 0) or 0)

        sorted_ranking = sorted(ranking.values(), key=lambda x: x["call_count"], reverse=True)[:limit]

        return api_success(data={"ranking": sorted_ranking})
    except Exception as e:
        logger.error(f"Model ranking error: user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "用量查询失败")
