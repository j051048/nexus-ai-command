"""用量统计和额度告警 API 路由"""

import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import get_current_user_id
from app.core.errors import api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/usage", tags=["Usage"])


def _get_admin_db():
    """获取 admin client (绕过 RLS, 因为 llm_usage_stats 的 RLS 依赖 app.current_org_id)"""
    from app.core.database import supabase

    return supabase


@router.get("/quota-alert")
async def get_quota_alert(req: Request, user_id: str = Depends(get_current_user_id)):
    """
    检查组织的 LLM 额度并返回告警信息
    """
    try:
        db = _get_admin_db()
        org_id = getattr(req.state, "org_id", None)

        if not db or not org_id:
            return api_success(data={"has_alert": False, "message": ""})

        result = (
            await db.table("llm_usage_stats")
            .select("*")
            .eq("tenant_id", str(org_id))
            .maybe_single()
            .execute()
        )

        if result and result.data:
            used = result.data.get("token_used", 0)
            limit = result.data.get("token_limit", 1000000)

            if used > limit * 0.9:
                return api_success(
                    data={
                        "has_alert": True,
                        "message": f"您的 Token 使用量已达到 {int(used/limit*100)}%，请及时充值以免影响业务。",
                        "level": "warning" if used < limit else "critical",
                    }
                )

        return api_success(data={"has_alert": False, "message": ""})

    except Exception as e:
        logger.error(f"Failed to fetch quota alert: {e}")
        return api_success(data={"has_alert": False, "message": "暂时无法获取额度状态"})


@router.get("/cost-alerts")
async def get_cost_alerts(
    req: Request,
    days: int = Query(default=1, ge=1, le=30),
    user_id: str = Depends(get_current_user_id),
):
    """Return actionable LLM/Agent cost alerts for the current tenant."""
    try:
        db = _get_admin_db()
        org_id = getattr(req.state, "org_id", None)
        if not db or not org_id:
            return api_success(data={"alerts": [], "summary": {"total_cost_usd": 0}})

        since = (date.today() - timedelta(days=days - 1)).isoformat()
        usage_res = (
            await db.table("llm_usage_stats")
            .select(
                "model_code,total_input_tokens,total_output_tokens,total_calls,total_cost,stat_date"
            )
            .eq("tenant_id", str(org_id))
            .gte("stat_date", since)
            .execute()
        )
        rows = usage_res.data or []
        total_cost = float(sum(r.get("total_cost", 0) for r in rows))
        total_tokens = sum(
            r.get("total_input_tokens", 0) + r.get("total_output_tokens", 0)
            for r in rows
        )

        quota_res = (
            await db.table("llm_quota_config")
            .select("monthly_token_limit,monthly_cost_limit")
            .eq("tenant_id", str(org_id))
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        quota = (quota_res.data or [{}])[0] if quota_res.data else {}
        monthly_cost_limit = float(quota.get("monthly_cost_limit") or 100)
        daily_cost_limit = float(monthly_cost_limit / 30)

        alerts: list[dict] = []
        if daily_cost_limit and total_cost >= daily_cost_limit * 0.9:
            alerts.append(
                {
                    "level": "critical" if total_cost >= daily_cost_limit else "warning",
                    "type": "daily_cost_budget",
                    "message": f"近 {days} 天 LLM 成本 ${total_cost:.4f} 接近日预算 ${daily_cost_limit:.2f}",
                    "action": "检查高成本模型和 Agent Run，必要时启用经济模型路由",
                }
            )

        model_costs: dict[str, dict] = {}
        for row in rows:
            model = row.get("model_code") or "unknown"
            if model not in model_costs:
                model_costs[model] = {"model_code": model, "cost_usd": 0.0, "calls": 0}
            model_costs[model]["cost_usd"] += float(row.get("total_cost", 0))
            model_costs[model]["calls"] += int(row.get("total_calls", 0) or 0)

        top_models = sorted(
            model_costs.values(), key=lambda item: item["cost_usd"], reverse=True
        )[:5]
        if (
            top_models
            and total_cost > 0
            and top_models[0]["cost_usd"] / total_cost >= 0.6
        ):
            alerts.append(
                {
                    "level": "warning",
                    "type": "model_cost_concentration",
                    "message": f"{top_models[0]['model_code']} 占近 {days} 天成本超过 60%",
                    "action": "确认该模型是否仅用于复杂/高风险任务，避免普通任务误走强模型",
                }
            )

        run_res = (
            await db.table("agent_runs")
            .select("id,run_id,status,cost_usd,total_cost,updated_at,input_summary")
            .eq("organization_id", str(org_id))
            .order("updated_at", desc=True)
            .limit(100)
            .execute()
        )
        high_cost_runs = []
        for row in run_res.data or []:
            cost = float(row.get("cost_usd") or row.get("total_cost") or 0)
            if cost >= max(1.0, daily_cost_limit * 0.2):
                high_cost_runs.append(
                    {
                        "id": row.get("id"),
                        "run_id": row.get("run_id"),
                        "status": row.get("status"),
                        "cost_usd": cost,
                        "summary": (row.get("input_summary") or "")[:160],
                    }
                )
        if high_cost_runs:
            alerts.append(
                {
                    "level": "warning",
                    "type": "high_cost_agent_run",
                    "message": f"发现 {len(high_cost_runs)} 条高成本 Agent Run",
                    "action": "进入 Agent Run 管理台复盘工具调用和反思循环",
                }
            )

        return api_success(
            data={
                "alerts": alerts,
                "summary": {
                    "period_days": days,
                    "total_cost_usd": round(total_cost, 6),
                    "total_tokens": total_tokens,
                    "daily_cost_limit_usd": daily_cost_limit,
                    "monthly_cost_limit_usd": monthly_cost_limit,
                    "top_models": top_models,
                    "high_cost_runs": high_cost_runs[:10],
                },
            }
        )
    except Exception as e:
        logger.error(f"Failed to fetch cost alerts: {e}")
        return api_success(data={"alerts": [], "summary": {"total_cost_usd": 0}})


@router.get("/current")
async def get_current_usage(req: Request, user_id: str = Depends(get_current_user_id)):
    """获取当前用量摘要（token/费用/请求数 + 配额限制）"""
    try:
        db = _get_admin_db()
        org_id = getattr(req.state, "org_id", None)

        if not db or not org_id:
            return api_success(
                data={
                    "tokens_used": 0,
                    "cost_usd": 0,
                    "requests": 0,
                    "tokens_limit": 1000000,
                    "cost_limit_usd": 100,
                }
            )

        first_of_month = date.today().replace(day=1).isoformat()
        usage_res = (
            await db.table("llm_usage_stats")
            .select("total_input_tokens,total_output_tokens,total_calls,total_cost")
            .eq("tenant_id", str(org_id))
            .gte("stat_date", first_of_month)
            .execute()
        )
        rows = usage_res.data or []
        tokens_used = sum(
            r.get("total_input_tokens", 0) + r.get("total_output_tokens", 0)
            for r in rows
        )
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

        return api_success(
            data={
                "tokens_used": tokens_used,
                "cost_usd": cost_usd,
                "requests": requests,
                "tokens_limit": tokens_limit,
                "cost_limit_usd": cost_limit_usd,
            }
        )
    except Exception as e:
        logger.error(f"Failed to fetch current usage: {e}")
        return api_success(
            data={
                "tokens_used": 0,
                "cost_usd": 0,
                "requests": 0,
                "tokens_limit": 1000000,
                "cost_limit_usd": 100,
            }
        )


@router.get("/stats")
async def get_usage_stats(req: Request, user_id: str = Depends(get_current_user_id)):
    """获取详细用量统计"""
    try:
        db = _get_admin_db()
        org_id = getattr(req.state, "org_id", None)

        if not db or not org_id:
            return api_success(
                data={"recent_usage": [], "total_tokens": 0, "billing_cycle": "monthly"}
            )

        result = (
            await db.table("llm_usage_stats")
            .select("*")
            .eq("tenant_id", str(org_id))
            .order("stat_date", desc=True)
            .limit(10)
            .execute()
        )
        rows = result.data or []
        total_tokens = sum(
            r.get("total_input_tokens", 0) + r.get("total_output_tokens", 0)
            for r in rows
        )
        return api_success(
            data={
                "recent_usage": rows,
                "total_tokens": total_tokens,
                "billing_cycle": "monthly",
            }
        )
    except Exception as e:
        logger.error(f"Failed to fetch usage stats: {e}")
        return api_success(
            data={"recent_usage": [], "total_tokens": 0, "billing_cycle": "monthly"}
        )


@router.get("/history")
async def get_usage_history(
    req: Request,
    days: int = Query(default=30, ge=1, le=365),
    user_id: str = Depends(get_current_user_id),
):
    """获取按日聚合的历史用量"""
    try:
        db = _get_admin_db()
        org_id = getattr(req.state, "org_id", None)

        if not db or not org_id:
            return api_success(data={"history": []})

        since = (date.today() - timedelta(days=days)).isoformat()
        result = (
            await db.table("llm_usage_stats")
            .select(
                "stat_date,total_input_tokens,total_output_tokens,total_calls,total_cost"
            )
            .eq("tenant_id", str(org_id))
            .gte("stat_date", since)
            .execute()
        )
        # 按日聚合（保留 input/output token 分拆，供前端图表使用）
        daily: dict[str, dict] = {}
        for r in result.data or []:
            d = r.get("stat_date", "")
            if d not in daily:
                daily[d] = {
                    "date": d,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "cost": 0.0,
                    "requests": 0,
                }
            inp = r.get("total_input_tokens", 0)
            out = r.get("total_output_tokens", 0)
            daily[d]["input_tokens"] += inp
            daily[d]["output_tokens"] += out
            daily[d]["total_tokens"] += inp + out
            daily[d]["cost"] += float(r.get("total_cost", 0))
            daily[d]["requests"] += r.get("total_calls", 0)

        history = sorted(daily.values(), key=lambda x: x["date"])
        return api_success(data={"history": history})
    except Exception as e:
        logger.error(f"Failed to fetch usage history: {e}")
        return api_success(data={"history": []})


@router.get("/cost-report")
async def get_cost_report(
    req: Request,
    days: int = Query(default=30, ge=1, le=365),
    user_id: str = Depends(get_current_user_id),
):
    """获取费用报告（按部门 / 项目维度）"""
    try:
        db = _get_admin_db()
        org_id = getattr(req.state, "org_id", None)

        if not db or not org_id:
            return api_success(
                data={"total_tokens": 0, "total_cost_usd": 0, "period_days": days}
            )

        since = (date.today() - timedelta(days=days)).isoformat()
        result = (
            await db.table("llm_usage_stats")
            .select(
                "department_id,total_input_tokens,total_output_tokens,total_calls,total_cost"
            )
            .eq("tenant_id", str(org_id))
            .gte("stat_date", since)
            .execute()
        )
        rows = result.data or []
        total_tokens = sum(
            r.get("total_input_tokens", 0) + r.get("total_output_tokens", 0)
            for r in rows
        )
        total_cost = float(sum(r.get("total_cost", 0) for r in rows))

        by_department: dict[str, dict] = {}
        for r in rows:
            dept = str(r.get("department_id") or "未分配")
            if dept not in by_department:
                by_department[dept] = {"tokens": 0, "cost_usd": 0.0, "requests": 0}
            by_department[dept]["tokens"] += r.get("total_input_tokens", 0) + r.get(
                "total_output_tokens", 0
            )
            by_department[dept]["cost_usd"] += float(r.get("total_cost", 0))
            by_department[dept]["requests"] += r.get("total_calls", 0)

        return api_success(
            data={
                "by_department": by_department,
                "total_tokens": total_tokens,
                "total_cost_usd": total_cost,
                "period_days": days,
            }
        )
    except Exception as e:
        logger.error(f"Failed to fetch cost report: {e}")
        return api_success(
            data={"total_tokens": 0, "total_cost_usd": 0, "period_days": days}
        )


@router.get("/model-breakdown")
async def get_model_breakdown(
    req: Request,
    days: int = Query(default=30, ge=1, le=365),
    user_id: str = Depends(get_current_user_id),
):
    """获取按模型维度的详细分解"""
    try:
        db = _get_admin_db()
        org_id = getattr(req.state, "org_id", None)

        if not db or not org_id:
            return api_success(
                data={
                    "models": [],
                    "total_cost": 0,
                    "total_tokens": 0,
                    "total_requests": 0,
                    "period_days": days,
                }
            )

        since = (date.today() - timedelta(days=days)).isoformat()
        result = (
            await db.table("llm_usage_stats")
            .select(
                "model_code,total_input_tokens,total_output_tokens,total_calls,total_cost,success_count,fail_count,avg_exec_time_ms"
            )
            .eq("tenant_id", str(org_id))
            .gte("stat_date", since)
            .neq("model_code", "_all")
            .execute()
        )
        rows = result.data or []

        agg: dict[str, dict] = {}
        for r in rows:
            mc = r.get("model_code", "unknown")
            if mc not in agg:
                agg[mc] = {
                    "model_code": mc,
                    "requests": 0,
                    "success_count": 0,
                    "error_count": 0,
                    "total_tokens": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_cost": 0.0,
                    "avg_latency_ms": 0,
                    "_latency_sum": 0,
                    "_latency_cnt": 0,
                }
            a = agg[mc]
            a["requests"] += r.get("total_calls", 0)
            a["success_count"] += r.get("success_count", 0)
            a["error_count"] += r.get("fail_count", 0)
            inp = r.get("total_input_tokens", 0)
            out = r.get("total_output_tokens", 0)
            a["input_tokens"] += inp
            a["output_tokens"] += out
            a["total_tokens"] += inp + out
            a["total_cost"] += float(r.get("total_cost", 0))
            a["_latency_sum"] += r.get("avg_exec_time_ms", 0) * r.get("total_calls", 0)
            a["_latency_cnt"] += r.get("total_calls", 0)

        models = []
        for a in agg.values():
            a["avg_latency_ms"] = (
                int(a["_latency_sum"] / a["_latency_cnt"]) if a["_latency_cnt"] else 0
            )
            a["error_rate"] = (
                round(a["error_count"] / a["requests"], 4) if a["requests"] else 0
            )
            del a["_latency_sum"], a["_latency_cnt"]
            models.append(a)

        total_cost = sum(m["total_cost"] for m in models)
        total_tokens = sum(m["total_tokens"] for m in models)
        total_requests = sum(m["requests"] for m in models)

        return api_success(
            data={
                "models": models,
                "total_cost": total_cost,
                "total_tokens": total_tokens,
                "total_requests": total_requests,
                "period_days": days,
            }
        )
    except Exception as e:
        logger.error(f"Failed to fetch model breakdown: {e}")
        return api_success(
            data={
                "models": [],
                "total_cost": 0,
                "total_tokens": 0,
                "total_requests": 0,
                "period_days": days,
            }
        )
