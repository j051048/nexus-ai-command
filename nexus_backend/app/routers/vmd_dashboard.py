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
            .select(
                "model_code,total_input_tokens,total_output_tokens,"
                "total_calls,total_cost"
            )
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
