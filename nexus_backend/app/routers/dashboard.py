"""
Dashboard Router — boss-level analytics and summaries.

Extracted from main.py to follow single-responsibility principle.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/boss")
async def boss_dashboard(request: Request, user_id: str = Depends(get_current_user_id)):
    """
    Boss dashboard — pending approvals, abnormal expenses, top performers.

    Requires authentication AND boss role.
    Uses request.state.db for RLS-scoped access.
    """
    client = request.state.db

    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "Database connection unavailable")

    try:
        # Verify user has boss role
        user_res = await client.table("users").select("role").eq("id", user_id).single().execute()

        if not user_res.data or user_res.data.get("role") != "boss":
            raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "仅领导可访问此仪表板")

        # 1. Pending Approvals Count
        pending_res = (
            await client.table("approval_requests").select("count", count="exact").eq("status", "pending").execute()
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
            await client.table("users").select("name, score, total_bonus").order("score", desc=True).limit(3).execute()
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
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/alerts")
async def dashboard_alerts(request: Request, user_id: str = Depends(get_current_user_id)):
    """跨域数据一致性预警 — 返回当前存在的数据异常。"""
    from datetime import datetime, timedelta, timezone

    client = request.state.db
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "Database connection unavailable")

    CN_TZ = timezone(timedelta(hours=8))
    alerts: list[dict] = []

    # Rule 1: 已成交客户无活跃合同
    try:
        won = await client.table("customers").select("id, name").eq("stage", "customer").execute()
        if won.data:
            ids = [c["id"] for c in won.data]
            active = await client.table("contracts").select("customer_id").eq("status", "active").in_("customer_id", ids).execute()
            contracted = {c["customer_id"] for c in (active.data or [])}
            missing = [c for c in won.data if c["id"] not in contracted]
            if missing:
                alerts.append({
                    "type": "customer_no_contract",
                    "severity": "warning",
                    "title": "已成交客户无活跃合同",
                    "message": f"{len(missing)} 个已成交客户没有活跃合同",
                    "items": [{"id": c["id"], "name": c["name"]} for c in missing[:10]],
                    "action_url": "/crm",
                })
    except Exception as e:
        logger.warning("Alert rule 1 failed: %s", e)

    # Rule 2: 合同已过期但状态仍为活跃
    try:
        today = datetime.now(CN_TZ).date().isoformat()
        stale = await client.table("contracts").select("id, title, end_date").eq("status", "active").lt("end_date", today).execute()
        if stale.data:
            alerts.append({
                "type": "contract_past_due",
                "severity": "error",
                "title": "合同已过期未更新",
                "message": f"{len(stale.data)} 个合同已过期但状态仍为活跃",
                "items": [{"id": c["id"], "title": c["title"], "end_date": c["end_date"]} for c in stale.data[:10]],
                "action_url": "/contracts",
            })
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
            alerts.append({
                "type": "contract_expiring_soon",
                "severity": "info",
                "title": "合同即将到期",
                "message": f"{len(expiring.data)} 个合同将在30天内到期",
                "items": [{"id": c["id"], "title": c["title"], "end_date": c["end_date"]} for c in expiring.data[:10]],
                "action_url": "/contracts",
            })
    except Exception as e:
        logger.warning("Alert rule 3 failed: %s", e)

    return api_success(data=alerts)


@router.get("/ai-stats")
async def ai_activity_stats(request: Request, user_id: str = Depends(get_current_user_id)):
    """AI 活跃度统计 — 本周完成任务数、预估节省时间、活跃 Agent 数。"""
    from datetime import datetime, timedelta, timezone

    client = request.state.db
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "Database connection unavailable")

    CN_TZ = timezone(timedelta(hours=8))
    now = datetime.now(CN_TZ)
    # Start of this week (Monday)
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0).isoformat()

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
        logger.debug("AI stats tasks query failed: %s", e)

    try:
        # Count distinct active agent sessions this week
        res = await (
            client.table("agent_tasks")
            .select("conversation_id")
            .gte("created_at", week_start)
            .execute()
        )
        if res.data:
            active_agents = len({r.get("conversation_id") for r in res.data if r.get("conversation_id")})
    except Exception as e:
        logger.debug("AI stats agents query failed: %s", e)

    # Estimate: ~15 min saved per completed task
    estimated_hours = round(tasks_completed * 0.25, 1)

    return api_success(data={
        "tasks_completed": tasks_completed,
        "estimated_hours_saved": estimated_hours,
        "active_agents": max(active_agents, 1),
    })
