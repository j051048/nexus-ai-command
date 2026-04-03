"""VMD 仪表盘路由"""

import logging

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vmd/dashboard", tags=["VMD Dashboard"])


@router.get("/model-usage")
async def get_model_usage(req: Request, user_id: str = Depends(get_current_user_id)):
    """获取按模型维度聚合的用量统计"""
    try:
        db = getattr(req.state, "db", None)
        org_id = getattr(req.state, "org_id", None)

        if not db or not org_id:
            return api_success(data={"usage": []})

        result = (
            await db.table("llm_usage_stats")
            .select("model_code,total_input_tokens,total_output_tokens," "total_calls,total_cost")
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
        db = getattr(req.state, "db", None)
        if not db:
            return api_success(data={"clues_count": 0, "tasks_count": 0, "compliance_issues": 0, "active_agents": 0})

        # 1. 商机线索数 (business_clue)
        clues_res = await db.table("business_clue").select("id", count="exact").execute()
        clues_count = clues_res.count if clues_res.count is not None else 0

        # 2. 正在执行的任务数 (vmd_main_task)
        tasks_res = await db.table("vmd_main_task").select("id", count="exact").neq("status", "completed").execute()
        tasks_count = tasks_res.count if tasks_res.count is not None else 0

        # 3. 合规风险数 (compliance_rule)
        compliance_res = await db.table("compliance_rule").select("id", count="exact").execute()
        compliance_count = compliance_res.count if compliance_res.count is not None else 0

        # 4. 活跃 Agent 数
        agents_res = await db.table("vmd_agent_config").select("id", count="exact").eq("is_active", True).execute()
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
