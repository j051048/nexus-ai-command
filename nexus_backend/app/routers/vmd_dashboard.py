"""VMD Dashboard API - Overview statistics and trend data endpoints."""

import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vmd/dashboard", tags=["VMD Dashboard"])


# ---------------------------------------------------------------------------
# Overview statistics
# ---------------------------------------------------------------------------


@router.get("/stats")
async def get_overview_stats(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取VMD概览统计（今日任务、活跃Agent、新线索、待审核）"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        today_str = datetime.now(UTC).strftime("%Y-%m-%d")

        # Today's tasks
        today_tasks_res = (
            await client.table("vmd_main_task")
            .select("id", count="exact")
            .eq("tenant_id", org_id)
            .gte("create_time", f"{today_str}T00:00:00")
            .execute()
        )
        today_tasks = today_tasks_res.count if today_tasks_res.count is not None else len(today_tasks_res.data or [])

        # Active agents
        active_agents_res = (
            await client.table("vmd_agent_config")
            .select("id", count="exact")
            .eq("tenant_id", org_id)
            .eq("is_active", True)
            .execute()
        )
        active_agents = (
            active_agents_res.count if active_agents_res.count is not None else len(active_agents_res.data or [])
        )

        # New clues (today)
        new_clues_res = (
            await client.table("business_clue")
            .select("id", count="exact")
            .eq("tenant_id", org_id)
            .eq("status", "new")
            .gte("create_time", f"{today_str}T00:00:00")
            .execute()
        )
        new_clues = new_clues_res.count if new_clues_res.count is not None else len(new_clues_res.data or [])

        # Pending review sub-tasks
        pending_review_res = (
            await client.table("vmd_sub_task").select("id", count="exact").eq("review_status", "pending").execute()
        )
        pending_review = (
            pending_review_res.count if pending_review_res.count is not None else len(pending_review_res.data or [])
        )

        return api_success(
            data={
                "today_tasks": today_tasks,
                "active_agents": active_agents,
                "new_clues": new_clues,
                "pending_review": pending_review,
            }
        )
    except Exception as e:
        logger.error(f"Dashboard stats error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---------------------------------------------------------------------------
# Task completion trend
# ---------------------------------------------------------------------------


@router.get("/task-trend")
async def get_task_trend(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    days: int = Query(30, ge=1, le=365, description="过去N天"),
):
    """获取任务完成趋势（按日分组）"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        start_date = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")

        res = (
            await client.table("vmd_main_task")
            .select("create_time, status")
            .eq("tenant_id", org_id)
            .gte("create_time", f"{start_date}T00:00:00")
            .order("create_time", desc=False)
            .execute()
        )
        tasks = res.data or []

        # Group by date
        trend: dict = defaultdict(lambda: {"date": "", "total": 0, "completed": 0, "failed": 0})
        for task in tasks:
            date_key = str(task.get("create_time", ""))[:10]
            trend[date_key]["date"] = date_key
            trend[date_key]["total"] += 1
            status = task.get("status", "")
            if status == "completed":
                trend[date_key]["completed"] += 1
            elif status == "failed":
                trend[date_key]["failed"] += 1

        trend_list = sorted(trend.values(), key=lambda x: x["date"])
        return api_success(data={"trend": trend_list, "days": days})
    except Exception as e:
        logger.error(f"Task trend error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---------------------------------------------------------------------------
# Agent workload distribution
# ---------------------------------------------------------------------------


@router.get("/agent-workload")
async def get_agent_workload(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取Agent工作量分布"""
    try:
        _org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        res = await client.table("vmd_sub_task").select("agent_code, status").execute()
        sub_tasks = res.data or []

        # Group by agent_code
        workload: dict = defaultdict(
            lambda: {
                "agent_code": "",
                "total": 0,
                "completed": 0,
                "running": 0,
                "failed": 0,
            }
        )
        for st in sub_tasks:
            agent = st.get("agent_code", "unknown")
            workload[agent]["agent_code"] = agent
            workload[agent]["total"] += 1
            status = st.get("status", "")
            if status == "completed":
                workload[agent]["completed"] += 1
            elif status in ("executing", "running"):
                workload[agent]["running"] += 1
            elif status == "failed":
                workload[agent]["failed"] += 1

        workload_list = sorted(workload.values(), key=lambda x: x["total"], reverse=True)
        return api_success(data={"workload": workload_list})
    except Exception as e:
        logger.error(f"Agent workload error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---------------------------------------------------------------------------
# Scene distribution
# ---------------------------------------------------------------------------


@router.get("/scene-distribution")
async def get_scene_distribution(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取任务场景分布"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        res = await client.table("vmd_main_task").select("scene_code, status").eq("tenant_id", org_id).execute()
        tasks = res.data or []

        # Group by scene_code
        distribution: dict = defaultdict(lambda: {"scene_code": "", "total": 0, "completed": 0})
        for task in tasks:
            scene = task.get("scene_code", "unknown")
            distribution[scene]["scene_code"] = scene
            distribution[scene]["total"] += 1
            if task.get("status") == "completed":
                distribution[scene]["completed"] += 1

        dist_list = sorted(distribution.values(), key=lambda x: x["total"], reverse=True)
        return api_success(data={"distribution": dist_list})
    except Exception as e:
        logger.error(f"Scene distribution error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---------------------------------------------------------------------------
# Model usage summary
# ---------------------------------------------------------------------------


@router.get("/model-usage")
async def get_model_usage(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取LLM模型使用汇总"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        res = (
            await client.table("llm_call_log")
            .select("model_code, input_tokens, output_tokens, call_cost, status")
            .eq("tenant_id", org_id)
            .execute()
        )
        logs = res.data or []

        # Group by model_code
        usage: dict = defaultdict(
            lambda: {
                "model_code": "",
                "call_count": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0.0,
                "success_count": 0,
                "error_count": 0,
            }
        )
        for log in logs:
            model = log.get("model_code", "unknown")
            usage[model]["model_code"] = model
            usage[model]["call_count"] += 1
            usage[model]["total_input_tokens"] += log.get("input_tokens", 0) or 0
            usage[model]["total_output_tokens"] += log.get("output_tokens", 0) or 0
            usage[model]["total_cost"] += float(log.get("call_cost", 0) or 0)
            if log.get("status") == "success":
                usage[model]["success_count"] += 1
            else:
                usage[model]["error_count"] += 1

        # Round costs
        for item in usage.values():
            item["total_cost"] = round(item["total_cost"], 4)

        usage_list = sorted(usage.values(), key=lambda x: x["call_count"], reverse=True)
        return api_success(data={"usage": usage_list})
    except Exception as e:
        logger.error(f"Model usage error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---------------------------------------------------------------------------
# Compliance check trend
# ---------------------------------------------------------------------------


@router.get("/compliance-trend")
async def get_compliance_trend(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    days: int = Query(30, ge=1, le=365, description="过去N天"),
):
    """获取合规检查趋势（按日分组）"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        start_date = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")

        res = (
            await client.table("compliance_check_log")
            .select("created_at, total_issues, error_count, warning_count")
            .eq("tenant_id", org_id)
            .gte("created_at", f"{start_date}T00:00:00")
            .order("created_at", desc=False)
            .execute()
        )
        logs = res.data or []

        # Group by date
        trend: dict = defaultdict(
            lambda: {
                "date": "",
                "total_checks": 0,
                "passed": 0,
                "has_issues": 0,
                "total_issues_found": 0,
            }
        )
        for log in logs:
            date_key = str(log.get("created_at", ""))[:10]
            trend[date_key]["date"] = date_key
            trend[date_key]["total_checks"] += 1
            error_count = log.get("error_count", 0) or 0
            if error_count == 0:
                trend[date_key]["passed"] += 1
            else:
                trend[date_key]["has_issues"] += 1
            trend[date_key]["total_issues_found"] += log.get("total_issues", 0) or 0

        trend_list = sorted(trend.values(), key=lambda x: x["date"])
        return api_success(data={"trend": trend_list, "days": days})
    except Exception as e:
        logger.error(f"Compliance trend error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
