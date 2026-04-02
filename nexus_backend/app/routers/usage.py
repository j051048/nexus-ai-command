"""用量统计和额度告警 API 路由"""

import logging
from datetime import date, timedelta
from typing import Dict, Any
from fastapi import APIRouter, Depends, Query, Request
from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/usage", tags=["Usage"])

@router.get("/quota-alert")
async def get_quota_alert(req: Request, user_id: str = Depends(get_current_user_id)):
    """
    检查组织的 LLM 额度并返回告警信息
    """
    try:
        db = getattr(req.state, "db", None)
        org_id = getattr(req.state, "org_id", None)
        
        if not db or not org_id:
            # 基础数据缺失时不报错，返回空以便前端静默失败
            return api_success(data={"has_alert": False, "message": ""})

        # 1. 尝试从 tenant_quotas 获取配额信息 (假设 schema 中有这个表)
        # 这里使用简单逻辑：如果使用量超过 90% 则告警
        result = await db.table("llm_usage_stats").select("*").eq("organization_id", org_id).maybe_single().execute()
        
        if result.data:
            used = result.data.get("token_used", 0)
            limit = result.data.get("token_limit", 1000000) # 默认 1M tokens
            
            if used > limit * 0.9:
                return api_success(data={
                    "has_alert": True,
                    "message": f"您的 Token 使用量已达到 {int(used/limit*100)}%，请及时充值以免影响业务。",
                    "level": "warning" if used < limit else "critical"
                })

        return api_success(data={"has_alert": False, "message": ""})
        
    except Exception as e:
        logger.error(f"Failed to fetch quota alert: {e}")
        # 这里返回静默成功，避免全局崩溃
        return api_success(data={"has_alert": False, "message": "暂时无法获取额度状态"})

@router.get("/current")
async def get_current_usage(req: Request, user_id: str = Depends(get_current_user_id)):
    """获取当前用量摘要（token/费用/请求数 + 配额限制）"""
    try:
        db = getattr(req.state, "db", None)
        org_id = getattr(req.state, "org_id", None)

        if not db or not org_id:
            return api_success(data={
                "tokens_used": 0, "cost_usd": 0, "requests": 0,
                "tokens_limit": 1000000, "cost_limit_usd": 100,
            })

        # 聚合本月用量
        from datetime import date
        first_of_month = date.today().replace(day=1).isoformat()
        usage_res = (
            await db.table("llm_usage_stats")
            .select("total_input_tokens,total_output_tokens,total_calls,total_cost")
            .eq("tenant_id", str(org_id))
            .gte("stat_date", first_of_month)
            .execute()
        )
        rows = usage_res.data or []
        tokens_used = sum(r.get("total_input_tokens", 0) + r.get("total_output_tokens", 0) for r in rows)
        cost_usd = float(sum(r.get("total_cost", 0) for r in rows))
        requests = sum(r.get("total_calls", 0) for r in rows)

        # 获取配额配置
        quota_res = (
            await db.table("llm_quota_config")
            .select("monthly_token_limit,monthly_cost_limit")
            .eq("tenant_id", str(org_id))
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        quota = (quota_res.data or [{}])[0] if quota_res.data else {}
        tokens_limit = quota.get("monthly_token_limit") or 1000000
        cost_limit_usd = float(quota.get("monthly_cost_limit") or 100)

        return api_success(data={
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
            "requests": requests,
            "tokens_limit": tokens_limit,
            "cost_limit_usd": cost_limit_usd,
        })
    except Exception as e:
        logger.error(f"Failed to fetch current usage: {e}")
        return api_success(data={
            "tokens_used": 0, "cost_usd": 0, "requests": 0,
            "tokens_limit": 1000000, "cost_limit_usd": 100,
        })


@router.get("/stats")
async def get_usage_stats(req: Request, user_id: str = Depends(get_current_user_id)):
    """
    获取详细用量统计
    """
    try:
        db = getattr(req.state, "db", None)
        org_id = getattr(req.state, "org_id", None)
        
        if not db or not org_id:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "上下文缺失")

        # 从 llm_usage_stats 或 user_token_usage 聚合数据
        result = await db.table("user_token_usage").select("*").eq("organization_id", org_id).limit(10).execute()
        
        return api_success(data={
            "recent_usage": result.data or [],
            "total_tokens": 0, # 这里可以增加更复杂的聚合逻辑
            "billing_cycle": "monthly"
        })
    except Exception as e:
        logger.error(f"Failed to fetch usage stats: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, f"获取统计失败: {str(e)}")
