"""
Dashboard Router — boss-level analytics and summaries.

Extracted from main.py to follow single-responsibility principle.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.auth import get_current_user_id
from app.core.dependencies import get_request_db
from app.core.errors import ErrorCode, api_error, api_success
from app.services.agent_slo_cost_service import summarize_agent_slo_cost

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/boss")
async def boss_dashboard(request: Request, user_id: str = Depends(get_current_user_id)):
    """
    Boss dashboard — pending approvals, abnormal expenses, top performers.

    Requires authentication AND boss role.
    Uses get_request_db(request) for RLS-scoped access.
    """
    client = get_request_db(request)

    if not client:
        raise api_error(
            ErrorCode.DB_CONNECTION_ERROR, "Database connection unavailable"
        )

    try:
        # Verify user has boss role
        user_res = (
            await client.table("users")
            .select("role")
            .eq("id", user_id)
            .single()
            .execute()
        )

        if not user_res.data or user_res.data.get("role") != "boss":
            raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "仅领导可访问此仪表板")

        # 1. Pending Approvals Count
        pending_res = (
            await client.table("approval_requests")
            .select("count", count="exact")
            .eq("status", "pending")
            .execute()
        )
        pending_count = pending_res.count if pending_res.count is not None else 0

        # 2. Abnormal Expenses (high amount pending)
        abnormal_res = (
            await client.table("approval_requests")
            .select("id, description, amount, users:submitted_by(name)")
            .eq("status", "pending")
            .eq("type", "expense")
            .gt("amount", 1000)
            .order("amount", desc=True)
            .limit(5)
            .execute()
        )

        abnormal_expenses = []
        for item in abnormal_res.data:
            user_name = "Unknown"
            if item.get("users"):
                user_name = item["users"].get("name", "Unknown")

            abnormal_expenses.append(
                {
                    "id": item["id"],
                    "user": user_name,
                    "amount": item["amount"],
                    "reason": item.get("description", "No description"),
                }
            )

        # 3. Top Performers
        users_res = (
            await client.table("users")
            .select("name, score, total_bonus")
            .order("score", desc=True)
            .limit(3)
            .execute()
        )

        top_performers = [u["name"] for u in users_res.data]

        return api_success(
            data={
                "pending_approvals": pending_count,
                "abnormal_expenses": abnormal_expenses,
                "top_performers": top_performers,
                "system_status": "Healthy",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching boss dashboard data: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "仪表盘数据获取失败")


@router.get("/alerts")
async def dashboard_alerts(
    request: Request, user_id: str = Depends(get_current_user_id)
):
    """跨域数据一致性预警 — 返回当前存在的数据异常。"""
    from datetime import datetime, timedelta, timezone

    client = get_request_db(request)
    if not client:
        raise api_error(
            ErrorCode.DB_CONNECTION_ERROR, "Database connection unavailable"
        )

    CN_TZ = timezone(timedelta(hours=8))
    alerts: list[dict] = []

    # Rule 1: 已成交客户无活跃合同
    try:
        won = (
            await client.table("customers")
            .select("id, name")
            .eq("stage", "customer")
            .execute()
        )
        if won.data:
            ids = [c["id"] for c in won.data]
            active = (
                await client.table("contracts")
                .select("customer_id")
                .eq("status", "active")
                .in_("customer_id", ids)
                .execute()
            )
            contracted = {c["customer_id"] for c in (active.data or [])}
            missing = [c for c in won.data if c["id"] not in contracted]
            if missing:
                alerts.append(
                    {
                        "type": "customer_no_contract",
                        "severity": "warning",
                        "title": "已成交客户无活跃合同",
                        "message": f"{len(missing)} 个已成交客户没有活跃合同",
                        "items": [
                            {"id": c["id"], "name": c["name"]} for c in missing[:10]
                        ],
                        "action_url": "/crm",
                    }
                )
    except Exception as e:
        logger.warning("Alert rule 1 failed: %s", e)

    # Rule 2: 合同已过期但状态仍为活跃
    try:
        today = datetime.now(CN_TZ).date().isoformat()
        stale = (
            await client.table("contracts")
            .select("id, title, end_date")
            .eq("status", "active")
            .lt("end_date", today)
            .execute()
        )
        if stale.data:
            alerts.append(
                {
                    "type": "contract_past_due",
                    "severity": "error",
                    "title": "合同已过期未更新",
                    "message": f"{len(stale.data)} 个合同已过期但状态仍为活跃",
                    "items": [
                        {"id": c["id"], "title": c["title"], "end_date": c["end_date"]}
                        for c in stale.data[:10]
                    ],
                    "action_url": "/contracts",
                }
            )
    except Exception as e:
        logger.warning("Alert rule 2 failed: %s", e)

    # Rule 3: 30天内即将到期合同
    try:
        today_d = datetime.now(CN_TZ).date()
        deadline = (today_d + timedelta(days=30)).isoformat()
        expiring = await (
            client.table("contracts")
            .select("id, title, end_date")
            .eq("status", "active")
            .gte("end_date", today_d.isoformat())
            .lte("end_date", deadline)
            .execute()
        )
        if expiring.data:
            alerts.append(
                {
                    "type": "contract_expiring_soon",
                    "severity": "info",
                    "title": "合同即将到期",
                    "message": f"{len(expiring.data)} 个合同将在30天内到期",
                    "items": [
                        {"id": c["id"], "title": c["title"], "end_date": c["end_date"]}
                        for c in expiring.data[:10]
                    ],
                    "action_url": "/contracts",
                }
            )
    except Exception as e:
        logger.warning("Alert rule 3 failed: %s", e)

    return api_success(data=alerts)


@router.get("/ai-stats")
async def ai_activity_stats(
    request: Request, user_id: str = Depends(get_current_user_id)
):
    """AI 活跃度统计 — 本周完成任务数、预估节省时间、活跃 Agent 数。"""
    from datetime import datetime, timedelta, timezone

    client = get_request_db(request)
    if not client:
        raise api_error(
            ErrorCode.DB_CONNECTION_ERROR, "Database connection unavailable"
        )

    CN_TZ = timezone(timedelta(hours=8))
    now = datetime.now(CN_TZ)
    # Start of this week (Monday)
    week_start = (
        (now - timedelta(days=now.weekday()))
        .replace(hour=0, minute=0, second=0)
        .isoformat()
    )

    tasks_completed = 0
    active_agents = 0

    try:
        # Count completed agent tasks this week
        res = await (
            client.table("agent_tasks")
            .select("id", count="exact")
            .eq("status", "done")
            .gte("updated_at", week_start)
            .execute()
        )
        tasks_completed = res.count if res.count is not None else 0
    except Exception as e:
        logger.error("AI stats tasks query failed: %s", e)

    try:
        # Count distinct active agent sessions this week
        res = (
            await client.table("agent_tasks")
            .select("conversation_id")
            .gte("created_at", week_start)
            .execute()
        )
        if res.data:
            active_agents = len(
                {r.get("conversation_id") for r in res.data if r.get("conversation_id")}
            )
    except Exception as e:
        logger.error("AI stats agents query failed: %s", e)

    # Estimate: ~15 min saved per completed task
    estimated_hours = round(tasks_completed * 0.25, 1)

    return api_success(
        data={
            "tasks_completed": tasks_completed,
            "estimated_hours_saved": estimated_hours,
            "active_agents": max(active_agents, 1),
        }
    )


@router.get("/roi")
async def ai_roi_dashboard(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    days: int = 30,
):
    """AI ROI 仪表盘 — 投资回报率、节省时间/成本、操作分布。"""
    from datetime import datetime, timedelta, timezone

    client = get_request_db(request)
    if not client:
        raise api_error(
            ErrorCode.DB_CONNECTION_ERROR, "Database connection unavailable"
        )

    days = min(max(days, 1), 365)
    CN_TZ = timezone(timedelta(hours=8))
    start_date = (datetime.now(CN_TZ) - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        # Get user's org_id
        user_res = (
            await client.table("users")
            .select("org_id")
            .eq("id", user_id)
            .single()
            .execute()
        )
        org_id = (user_res.data or {}).get("org_id")
    except Exception:
        org_id = None

    if not org_id:
        return api_success({"days": [], "summary": {}})

    # Fetch daily ROI data
    try:
        roi_res = (
            await client.table("ai_roi_daily")
            .select("*")
            .eq("tenant_id", org_id)
            .gte("metric_date", start_date)
            .order("metric_date", desc=False)
            .execute()
        )
        rows = roi_res.data or []
    except Exception as e:
        logger.error("ROI query failed: %s", e)
        rows = []

    # Aggregate summary
    summary = {
        "total_ai_cost": 0,
        "total_tokens": 0,
        "total_llm_calls": 0,
        "total_tool_calls": 0,
        "total_tool_success": 0,
        "total_minutes_saved": 0,
        "total_labor_saved": 0,
        "avg_roi_percent": 0,
        "total_positive_feedback": 0,
        "total_negative_feedback": 0,
        "avg_response_time_ms": 0,
    }
    by_category = {
        "approval": 0,
        "crm": 0,
        "report": 0,
        "attendance": 0,
        "finance": 0,
        "leave": 0,
        "schedule": 0,
        "knowledge": 0,
        "other": 0,
    }

    if rows:
        total_cost = 0.0
        total_saved = 0.0
        total_rt = 0
        for r in rows:
            summary["total_ai_cost"] += float(r.get("ai_cost_usd") or 0)
            summary["total_tokens"] += int(r.get("total_tokens") or 0)
            summary["total_llm_calls"] += int(r.get("total_llm_calls") or 0)
            summary["total_tool_calls"] += int(r.get("tool_calls_total") or 0)
            summary["total_tool_success"] += int(r.get("tool_calls_success") or 0)
            summary["total_minutes_saved"] += float(
                r.get("estimated_minutes_saved") or 0
            )
            summary["total_labor_saved"] += float(
                r.get("estimated_labor_cost_saved") or 0
            )
            summary["total_positive_feedback"] += int(r.get("positive_feedback") or 0)
            summary["total_negative_feedback"] += int(r.get("negative_feedback") or 0)
            total_rt += int(r.get("avg_response_time_ms") or 0)

            for cat in by_category:
                by_category[cat] += int(r.get(f"cat_{cat}") or 0)

            total_cost += float(r.get("ai_cost_usd") or 0)
            total_saved += float(r.get("estimated_labor_cost_saved") or 0)

        summary["total_ai_cost"] = round(summary["total_ai_cost"], 2)
        summary["total_labor_saved"] = round(summary["total_labor_saved"], 2)
        summary["total_minutes_saved"] = round(summary["total_minutes_saved"], 1)
        summary["avg_response_time_ms"] = int(total_rt / len(rows)) if rows else 0
        if total_cost > 0:
            summary["avg_roi_percent"] = round(
                (total_saved - total_cost) / total_cost * 100, 1
            )

    # Daily trend (simplified for frontend charts)
    daily = [
        {
            "date": r["metric_date"],
            "cost": float(r.get("ai_cost_usd") or 0),
            "saved": float(r.get("estimated_labor_cost_saved") or 0),
            "tool_calls": int(r.get("tool_calls_total") or 0),
            "minutes_saved": float(r.get("estimated_minutes_saved") or 0),
            "roi": float(r.get("roi_percent") or 0),
        }
        for r in rows
    ]

    return api_success(
        data={
            "summary": summary,
            "daily": daily,
            "by_category": by_category,
            "days": days,
        }
    )


@router.get("/roi/baselines")
async def ai_roi_baselines(
    request: Request,
    _user_id: str = Depends(get_current_user_id),
):
    """AI ROI 基线配置 — 各操作类别的人工耗时基线。"""
    client = get_request_db(request)
    if not client:
        raise api_error(
            ErrorCode.DB_CONNECTION_ERROR, "Database connection unavailable"
        )

    try:
        res = await client.table("ai_roi_baselines").select("*").execute()
        return api_success(data=res.data or [])
    except Exception as e:
        logger.error("ROI baselines query failed: %s", e)
        return api_success(data=[])


@router.get("/ai-weekly-report")
async def ai_weekly_report(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Business-facing weekly AI behavior report for leaders."""
    from datetime import datetime, timedelta, timezone

    client = get_request_db(request)
    if not client:
        raise api_error(
            ErrorCode.DB_CONNECTION_ERROR, "Database connection unavailable"
        )

    CN_TZ = timezone(timedelta(hours=8))
    now = datetime.now(CN_TZ)
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    week_start_iso = week_start.isoformat()

    actions_executed = 0
    successful_actions = 0
    human_overrides = 0
    failures_by_category: dict[str, int] = {}
    top_failed_scenarios: list[dict] = []
    risk_avoided = 0

    try:
        res = (
            await client.table("agent_tasks")
            .select("id,status,error_type,task_type,updated_at")
            .gte("updated_at", week_start_iso)
            .execute()
        )
        rows = res.data or []
        actions_executed = len(rows)
        successful_actions = len(
            [r for r in rows if r.get("status") in ("done", "success", "completed")]
        )
        for row in rows:
            if row.get("status") in ("failed", "error"):
                category = row.get("error_type") or "unknown"
                failures_by_category[category] = (
                    failures_by_category.get(category, 0) + 1
                )
        top_failed_scenarios = [
            {"category": category, "count": count}
            for category, count in sorted(
                failures_by_category.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:5]
        ]
    except Exception as e:
        logger.warning("AI weekly report agent task query failed: %s", e)

    try:
        res = (
            await client.table("agent_trust_reports")
            .select("human_overrides,risk_avoided,created_at")
            .gte("created_at", week_start_iso)
            .execute()
        )
        for row in res.data or []:
            human_overrides += int(row.get("human_overrides") or 0)
            risk_avoided += int(row.get("risk_avoided") or 0)
    except Exception as e:
        logger.info("AI weekly report trust query unavailable: %s", e)

    try:
        roi_res = (
            await client.table("ai_roi_daily")
            .select("estimated_minutes_saved,estimated_labor_cost_saved,metric_date")
            .gte("metric_date", week_start.date().isoformat())
            .execute()
        )
        estimated_minutes = sum(
            float(r.get("estimated_minutes_saved") or 0) for r in (roi_res.data or [])
        )
        estimated_savings = sum(
            float(r.get("estimated_labor_cost_saved") or 0)
            for r in (roi_res.data or [])
        )
    except Exception as e:
        logger.info("AI weekly report ROI query unavailable: %s", e)
        estimated_minutes = actions_executed * 15
        estimated_savings = successful_actions * 20

    success_rate = (
        round(successful_actions / actions_executed * 100, 1) if actions_executed else 0
    )
    report = {
        "generated_at": now.isoformat(),
        "week_start": week_start_iso,
        "actions_executed": actions_executed,
        "successful_actions": successful_actions,
        "success_rate": success_rate,
        "human_overrides": human_overrides,
        "risk_avoided": risk_avoided,
        "failures_by_category": failures_by_category,
        "top_failed_scenarios": top_failed_scenarios,
        "estimated_hours_saved": round(estimated_minutes / 60, 1),
        "estimated_savings": round(estimated_savings, 2),
        "audit_summary": (
            f"AI completed {successful_actions}/{actions_executed} actions this week; "
            f"{human_overrides} required human override."
        ),
        "recommendations": [
            "Review the top failed scenario queue before changing prompts.",
            "Enable autonomous execution only for low-risk, high-confidence actions.",
            "Use replay cases for every prompt or tool-policy change.",
        ],
    }
    return api_success(data=report)


@router.get("/agent-slo-cost")
async def agent_slo_cost_summary(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    days: int = 7,
):
    """Agent SLO and model-cost summary for production reliability reviews."""
    from datetime import datetime, timedelta, timezone

    client = get_request_db(request)
    if not client:
        raise api_error(
            ErrorCode.DB_CONNECTION_ERROR, "Database connection unavailable"
        )

    days = min(max(days, 1), 30)
    start_time = (
        datetime.now(timezone.utc) - timedelta(days=days)
    ).isoformat()

    try:
        user_res = (
            await client.table("users")
            .select("org_id,organization_id")
            .eq("id", user_id)
            .single()
            .execute()
        )
        user_row = user_res.data or {}
        org_id = user_row.get("organization_id") or user_row.get("org_id")
    except Exception:
        org_id = None

    agent_runs: list[dict] = []
    llm_calls: list[dict] = []

    try:
        query = (
            client.table("agent_runs")
            .select("status,duration_ms,cost_usd,total_cost,input_tokens,output_tokens,started_at,updated_at")
            .gte("started_at", start_time)
        )
        if org_id:
            query = query.eq("organization_id", org_id)
        res = await query.limit(500).execute()
        agent_runs = res.data or []
    except Exception as e:
        logger.info("Agent SLO run query unavailable: %s", e)

    try:
        query = (
            client.table("llm_call_log")
            .select("model_code,input_tokens,output_tokens,total_tokens,call_cost,exec_time_ms,status,create_time")
            .gte("create_time", start_time)
        )
        if org_id:
            query = query.eq("tenant_id", org_id)
        res = await query.limit(1000).execute()
        llm_calls = res.data or []
    except Exception as e:
        logger.info("Agent SLO LLM call query unavailable: %s", e)

    summary = summarize_agent_slo_cost(agent_runs=agent_runs, llm_calls=llm_calls)
    summary["window_days"] = days
    return api_success(data=summary)
