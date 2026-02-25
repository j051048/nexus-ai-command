"""Admin Agent Trace API - Debug panel endpoints for agent execution inspection."""

import logging
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.agent_trace_service import agent_trace_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin/traces", tags=["Admin Traces"])


@router.get("/stats")
async def get_trace_stats(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取Agent执行统计概览"""
    try:
        org_id = getattr(req.state, "org_id", None)
        stats = agent_trace_service.get_stats(org_id=org_id)
        return api_success(data=stats)
    except Exception as e:
        logger.error(f"Get trace stats error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/list")
async def list_traces(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    status: str | None = Query(None, description="按状态筛选: running/completed/failed"),
    limit: int = Query(50, ge=1, le=200),
):
    """获取Agent执行记录列表"""
    try:
        # Combine active and completed traces
        all_traces = list(agent_trace_service._active_traces.values()) + list(
            agent_trace_service._completed_traces.values()
        )

        # Filter by org_id
        org_id = getattr(req.state, "org_id", None)
        if org_id:
            all_traces = [t for t in all_traces if t.org_id == org_id]

        # Filter by status
        if status:
            all_traces = [t for t in all_traces if t.status.value == status]

        # Sort by start_time desc
        all_traces.sort(key=lambda t: t.start_time, reverse=True)

        # Limit
        all_traces = all_traces[:limit]

        items = []
        for t in all_traces:
            items.append(
                {
                    "trace_id": t.trace_id,
                    "thread_id": t.thread_id,
                    "user_id": t.user_id,
                    "query": t.query[:200] if t.query else "",
                    "status": t.status.value,
                    "start_time": datetime.fromtimestamp(t.start_time, tz=UTC).isoformat(),
                    "total_duration_ms": t.total_duration_ms,
                    "total_tokens": t.total_tokens,
                    "total_cost_usd": t.total_cost_usd,
                    "step_count": len(t.steps),
                    "tags": t.tags,
                }
            )

        return api_success(data={"traces": items, "total": len(items)})
    except Exception as e:
        logger.error(f"List traces error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/detail/{trace_id}")
async def get_trace_detail(
    trace_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """获取单个trace的详细执行步骤"""
    try:
        trace = agent_trace_service.get_trace(trace_id)
        if not trace:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, f"Trace not found: {trace_id}")

        return api_success(data={"trace": trace.to_dict()})
    except Exception as e:
        logger.error(f"Get trace detail error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/replay/{trace_id}")
async def replay_trace(
    trace_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """获取trace回放数据（步骤级别的输入/输出/工具调用）"""
    try:
        replay_data = agent_trace_service.replay_trace(trace_id)
        if "error" in replay_data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, replay_data["error"])

        return api_success(data=replay_data)
    except Exception as e:
        logger.error(f"Replay trace error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/metrics")
async def get_metrics(
    user_id: str = Depends(get_current_user_id),
    metric_name: str | None = Query(None, description="指标名称筛选"),
    hours: int = Query(24, ge=1, le=168, description="最近N小时"),
):
    """获取Agent执行指标数据"""
    try:
        since = time.time() - (hours * 3600)
        metrics = agent_trace_service.get_metrics(metric_name=metric_name, since=since)
        return api_success(data={"metrics": metrics, "count": len(metrics)})
    except Exception as e:
        logger.error(f"Get metrics error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/thread/{thread_id}")
async def get_thread_traces(
    thread_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """获取指定会话的所有trace记录"""
    try:
        traces = agent_trace_service.get_thread_traces(thread_id)
        items = [t.to_dict() for t in traces]
        return api_success(data={"traces": items, "total": len(items)})
    except Exception as e:
        logger.error(f"Get thread traces error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---------------------------------------------------------------------------
# AI Quality Dashboard endpoints
# ---------------------------------------------------------------------------


@router.get("/quality/summary")
async def get_quality_summary(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    days: int = Query(7, ge=1, le=90, description="统计天数"),
):
    """获取AI质量概览"""
    try:
        from app.services.ai_quality_service import ai_quality_service

        org_id = getattr(req.state, "org_id", None)
        client = getattr(req.state, "db", None)
        summary = await ai_quality_service.get_quality_summary(org_id, days, db=client)
        return api_success(data=summary)
    except Exception as e:
        logger.error(f"Quality summary error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/quality/trend")
async def get_quality_trend(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    days: int = Query(30, ge=1, le=90, description="趋势天数"),
):
    """获取AI质量趋势数据"""
    try:
        from app.services.ai_quality_service import ai_quality_service

        org_id = getattr(req.state, "org_id", None)
        client = getattr(req.state, "db", None)
        trend = await ai_quality_service.get_quality_trend(org_id, days, db=client)
        return api_success(data={"trend": trend, "days": days})
    except Exception as e:
        logger.error(f"Quality trend error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
