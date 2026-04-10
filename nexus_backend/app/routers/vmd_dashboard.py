"""VMD 仪表盘路由"""

import logging

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vmd/dashboard", tags=["VMD Dashboard"])


def _get_admin_db():
    """获取 admin client (绕过 RLS)"""
    from app.core.database import supabase

    return supabase


@router.get("/model-usage")
async def get_model_usage(req: Request, user_id: str = Depends(get_current_user_id)):
    """获取按模型维度聚合的用量统计"""
    try:
        db = _get_admin_db()
        org_id = getattr(req.state, "org_id", None)

        if not db or not org_id:
            return api_success(data={"usage": []})

        result = (
            await db.table("llm_usage_stats")
            .select("model_code,total_input_tokens,total_output_tokens," "total_calls,total_cost")
            .eq("tenant_id", str(org_id))
            .neq("model_code", "_all")
            .execute()
        )
        rows = result.data or []

        # 按 model_code 聚合
        agg: dict = {}
        for r in rows:
            mc = r.get("model_code", "unknown")
            if mc not in agg:
                agg[mc] = {
                    "model_code": mc,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "call_count": 0,
                    "total_cost": 0,
                }
            agg[mc]["total_input_tokens"] += r.get("total_input_tokens", 0)
            agg[mc]["total_output_tokens"] += r.get("total_output_tokens", 0)
            agg[mc]["call_count"] += r.get("total_calls", 0)
            agg[mc]["total_cost"] += float(r.get("total_cost", 0))

        return api_success(data={"usage": list(agg.values())})
    except Exception as e:
        logger.error(f"Failed to fetch model usage: {e}")
        return api_success(data={"usage": []})


@router.get("/stats")
async def get_dashboard_stats(req: Request, user_id: str = Depends(get_current_user_id)):
    """获取 VMD 仪表盘概览统计数据"""
    try:
        db = _get_admin_db()
        org_id = getattr(req.state, "org_id", None)
        if not db or not org_id:
            return api_success(data={"clues_count": 0, "tasks_count": 0, "compliance_issues": 0, "active_agents": 0})

        tenant_id = str(org_id)

        # 1. 商机线索数 (business_clue)
        clues_res = await db.table("business_clue").select("id", count="exact").eq("tenant_id", tenant_id).execute()
        clues_count = clues_res.count if clues_res.count is not None else 0

        # 2. 正在执行的任务数 (vmd_main_task)
        tasks_res = (
            await db.table("vmd_main_task")
            .select("id", count="exact")
            .eq("tenant_id", tenant_id)
            .neq("status", "completed")
            .execute()
        )
        tasks_count = tasks_res.count if tasks_res.count is not None else 0

        # 3. 合规风险数 (compliance_rule)
        compliance_res = (
            await db.table("compliance_rule").select("id", count="exact").eq("tenant_id", tenant_id).execute()
        )
        compliance_count = compliance_res.count if compliance_res.count is not None else 0

        # 4. 活跃 Agent 数
        agents_res = (
            await db.table("vmd_agent_config")
            .select("id", count="exact")
            .eq("tenant_id", tenant_id)
            .eq("is_active", True)
            .execute()
        )
        active_agents = agents_res.count if agents_res.count is not None else 0

        return api_success(
            data={
                "clues_count": clues_count,
                "tasks_count": tasks_count,
                "compliance_issues": compliance_count,
                "active_agents": active_agents,
            }
        )
    except Exception as e:
        logger.error(f"Failed to fetch VMD dashboard stats: {e}")
        return api_success(data={"clues_count": 0, "tasks_count": 0, "compliance_issues": 0, "active_agents": 0})


@router.get("/roi")
async def get_vmd_roi(req: Request, user_id: str = Depends(get_current_user_id)):
    """VMD ROI 仪表盘 — 成本节省、人工替代率、预算 vs 实际"""
    try:
        db = _get_admin_db()
        org_id = getattr(req.state, "org_id", None)
        if not db or not org_id:
            return api_success(data=_empty_roi())

        tenant_id = str(org_id)

        # 1. 已完成的 VMD 任务数
        done_tasks = await db.table("vmd_main_task").select("id,scene_code,created_at").eq("tenant_id", tenant_id).eq("status", "done").execute()
        done_count = len(done_tasks.data or [])

        # 2. LLM 成本（本月）
        from datetime import datetime
        month_start = datetime.now().replace(day=1).isoformat()[:10]
        cost_res = await db.table("llm_call_log").select("cost").eq("tenant_id", tenant_id).gte("created_at", month_start).execute()
        total_cost_usd = sum(float(r.get("cost", 0)) for r in (cost_res.data or []))

        # 3. 按场景统计已完成任务
        scene_counts: dict[str, int] = {}
        for t in (done_tasks.data or []):
            sc = t.get("scene_code", "other")
            scene_counts[sc] = scene_counts.get(sc, 0) + 1

        # 4. ROI 计算
        # 假设：手动任务 4h/个，AI 任务 0.5h/个，人工时薪 ¥150
        MANUAL_HOURS_PER_TASK = 4.0
        AI_HOURS_PER_TASK = 0.5
        HOURLY_RATE_CNY = 150.0
        USD_TO_CNY = 7.2

        manual_hours = done_count * MANUAL_HOURS_PER_TASK
        ai_hours = done_count * AI_HOURS_PER_TASK
        hours_saved = manual_hours - ai_hours
        labor_cost_saved = hours_saved * HOURLY_RATE_CNY
        ai_cost_cny = total_cost_usd * USD_TO_CNY
        net_savings = labor_cost_saved - ai_cost_cny
        roi_pct = (net_savings / ai_cost_cny * 100) if ai_cost_cny > 0 else 0

        # 5. 预算 vs 实际（日度，最近 7 天）
        from app.core.config import settings
        budget_daily = settings.TOKEN_BUDGET_MAX_COST_PER_DAY_PER_TENANT
        budget_monthly = settings.TOKEN_BUDGET_MAX_COST_PER_MONTH_PER_TENANT

        return api_success(data={
            "completed_tasks": done_count,
            "manual_hours_saved": round(hours_saved, 1),
            "labor_cost_saved_cny": round(labor_cost_saved, 2),
            "ai_cost_cny": round(ai_cost_cny, 2),
            "net_savings_cny": round(net_savings, 2),
            "roi_percentage": round(roi_pct, 1),
            "automation_rate": round((1 - AI_HOURS_PER_TASK / MANUAL_HOURS_PER_TASK) * 100, 1) if done_count > 0 else 0,
            "budget_daily_usd": budget_daily,
            "budget_monthly_usd": budget_monthly,
            "actual_monthly_usd": round(total_cost_usd, 2),
            "budget_utilization": round(total_cost_usd / budget_monthly * 100, 1) if budget_monthly > 0 else 0,
            "scene_savings": [
                {"scene": sc, "tasks": cnt, "hours_saved": round(cnt * (MANUAL_HOURS_PER_TASK - AI_HOURS_PER_TASK), 1),
                 "cost_saved_cny": round(cnt * (MANUAL_HOURS_PER_TASK - AI_HOURS_PER_TASK) * HOURLY_RATE_CNY, 2)}
                for sc, cnt in sorted(scene_counts.items(), key=lambda x: -x[1])
            ],
        })
    except Exception as e:
        logger.error(f"Failed to compute VMD ROI: {e}")
        return api_success(data=_empty_roi())


def _empty_roi() -> dict:
    return {
        "completed_tasks": 0, "manual_hours_saved": 0, "labor_cost_saved_cny": 0,
        "ai_cost_cny": 0, "net_savings_cny": 0, "roi_percentage": 0,
        "automation_rate": 0, "budget_daily_usd": 0, "budget_monthly_usd": 0,
        "actual_monthly_usd": 0, "budget_utilization": 0, "scene_savings": [],
    }
