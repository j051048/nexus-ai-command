"""
Report Engine Service
AI-generated SQL reports with scheduling and push delivery.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)


# ── Schema introspection ──────────────────────────────────────────────

_SCHEMA_INFO = """
核心表:
- customers: 客户表 (id, organization_id, name, company, industry, stage, source, estimated_value, assigned_to, created_at)
- customer_contacts: 联系人表 (id, customer_id, name, title, phone, email, is_primary)
- customer_activities: 活动表 (id, customer_id, user_id, activity_type, content, created_at)
- sales_orders: 订单表 (id, organization_id, customer_id, amount, status, created_at)
- users: 用户表 (id, organization_id, name, role, department)
- organizations: 组织表 (id, name, slug)
"""


# ── SQL safety ────────────────────────────────────────────────────────

def _is_safe_sql(sql: str) -> bool:
    sql_lower = sql.lower().strip()
    dangerous = ["drop", "delete", "update", "insert", "alter", "create", "truncate", "grant", "revoke"]
    return not any(kw in sql_lower for kw in dangerous) and sql_lower.startswith("select")


# ── NL-to-SQL generation ─────────────────────────────────────────────

async def generate_sql(nl_query: str, org_id: str) -> dict[str, Any]:
    """Generate SQL from natural language query using LLM."""
    try:
        from app.services.llm_helpers import get_langchain_llm_sync, resolve_model_config

        config = await resolve_model_config(scene_code="report_engine", complexity_tier="balanced")
        llm = get_langchain_llm_sync(**config)

        prompt = f"""你是一个SQL专家。根据用户的自然语言查询生成安全的PostgreSQL查询语句。

数据库Schema:
{_SCHEMA_INFO}

用户查询: {nl_query}

要求:
1. 只返回SELECT语句，不要UPDATE/DELETE/DROP
2. 必须使用 WHERE ... organization_id = '{org_id}' 进行租户隔离
3. 返回纯SQL，不要解释，不要markdown代码块
4. 限制最多返回200行 (LIMIT 200)
5. 时间字段使用 created_at，当前时间用 now()

SQL:"""

        sql = llm.invoke(prompt).content.strip()
        sql = sql.replace("```sql", "").replace("```", "").strip()

        if not _is_safe_sql(sql):
            return {"success": False, "error": "生成的SQL不安全，拒绝执行"}

        return {"success": True, "sql": sql}
    except Exception as e:
        logger.error(f"SQL generation failed: {e}")
        return {"success": False, "error": str(e)}


# ── SQL execution ────────────────────────────────────────────────────

async def execute_report_sql(sql: str) -> dict[str, Any]:
    """Execute a safe SQL query and return results."""
    if not _is_safe_sql(sql):
        return {"success": False, "error": "SQL不安全，拒绝执行"}
    try:
        result = await supabase.rpc("execute_safe_query", {"query_sql": sql}).execute()
        rows = result.data or []
        return {"success": True, "data": rows[:200], "total_rows": len(rows)}
    except Exception as e:
        logger.error(f"SQL execution failed: {e}")
        return {"success": False, "error": str(e)}


# ── Insight generation ───────────────────────────────────────────────

async def generate_insight(nl_query: str, data: list) -> str:
    """Generate AI insight summary from query results."""
    if not data:
        return "未找到相关数据"
    try:
        from app.services.llm_helpers import get_langchain_llm_sync, resolve_model_config

        config = await resolve_model_config(scene_code="report_engine", complexity_tier="light")
        llm = get_langchain_llm_sync(**config)

        prompt = f"""根据查询结果生成简洁的洞察分析（2-3句话，中文）。

用户查询: {nl_query}
结果数据(前5行): {data[:5]}
总行数: {len(data)}

洞察:"""

        return llm.invoke(prompt).content.strip()
    except Exception as e:
        logger.error(f"Insight generation failed: {e}")
        return "洞察生成失败"


# ── Chart config suggestion ──────────────────────────────────────────

def suggest_chart_config(data: list) -> dict[str, Any]:
    """Suggest chart type and config based on data shape."""
    if not data:
        return {"type": "none"}

    first = data[0]
    keys = list(first.keys())
    numeric_keys = [k for k in keys if isinstance(first.get(k), int | float)]
    string_keys = [k for k in keys if isinstance(first.get(k), str)]

    if len(numeric_keys) >= 1 and len(string_keys) >= 1:
        return {
            "type": "bar",
            "x_key": string_keys[0],
            "y_keys": numeric_keys[:3],
        }
    elif len(numeric_keys) >= 2:
        return {
            "type": "line",
            "x_key": keys[0],
            "y_keys": numeric_keys[:3],
        }
    return {"type": "table"}


# ── Saved reports CRUD ───────────────────────────────────────────────

async def save_report(
    org_id: str, user_id: str, title: str, nl_query: str,
    generated_sql: str, result_data: list, chart_config: dict,
    summary: str | None = None, is_public: bool = False,
) -> dict[str, Any]:
    """Save a generated report."""
    row = {
        "organization_id": org_id,
        "user_id": user_id,
        "title": title,
        "nl_query": nl_query,
        "generated_sql": generated_sql,
        "result_data": result_data,
        "chart_config": chart_config,
        "summary": summary,
        "is_public": is_public,
    }
    res = await supabase.table("saved_reports").insert(row).execute()
    return res.data[0] if res.data else {}


async def list_saved_reports(org_id: str, user_id: str, limit: int = 20) -> list:
    """List saved reports for org (own + public)."""
    # Own reports
    own = await supabase.table("saved_reports").select(
        "id, title, nl_query, summary, is_public, created_at"
    ).eq("organization_id", org_id).eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()

    # Public reports by others
    pub = await supabase.table("saved_reports").select(
        "id, title, nl_query, summary, is_public, created_at"
    ).eq("organization_id", org_id).eq("is_public", True).neq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()

    seen = {r["id"] for r in (own.data or [])}
    merged = list(own.data or [])
    for r in (pub.data or []):
        if r["id"] not in seen:
            merged.append(r)
    return merged


async def get_saved_report(report_id: str) -> dict | None:
    """Get a single saved report by ID."""
    res = await supabase.table("saved_reports").select("*").eq("id", report_id).maybe_single().execute()
    return res.data


async def delete_saved_report(report_id: str, user_id: str) -> bool:
    """Delete a saved report (only owner)."""
    res = await supabase.table("saved_reports").delete().eq("id", report_id).eq("user_id", user_id).execute()
    return bool(res.data)


# ── Report schedules CRUD ────────────────────────────────────────────

async def create_schedule(
    org_id: str, user_id: str, name: str, nl_query: str,
    schedule_type: str = "daily", hour: int = 9,
    day_of_week: int = 1, day_of_month: int = 1,
    recipients: list | None = None, output_format: str = "both",
) -> dict[str, Any]:
    """Create a report schedule."""
    next_exec = _compute_next_execution(schedule_type, hour, day_of_week, day_of_month)
    row = {
        "organization_id": org_id,
        "user_id": user_id,
        "name": name,
        "nl_query": nl_query,
        "schedule_type": schedule_type,
        "hour": hour,
        "day_of_week": day_of_week,
        "day_of_month": day_of_month,
        "recipients": recipients or [],
        "output_format": output_format,
        "next_execution_at": next_exec.isoformat(),
    }
    res = await supabase.table("report_schedules").insert(row).execute()
    return res.data[0] if res.data else {}


async def list_schedules(org_id: str) -> list:
    """List all active schedules for org."""
    res = await supabase.table("report_schedules").select(
        "id, name, nl_query, schedule_type, hour, day_of_week, day_of_month, "
        "recipients, output_format, is_active, last_executed_at, next_execution_at, "
        "failure_count, created_at"
    ).eq("organization_id", org_id).order("created_at", desc=True).execute()
    return res.data or []


async def toggle_schedule(schedule_id: str, active: bool) -> bool:
    """Toggle a schedule active/inactive."""
    res = await supabase.table("report_schedules").update({
        "is_active": active,
        "next_execution_at": _compute_next_execution_after_toggle(active).isoformat() if active else None,
    }).eq("id", schedule_id).execute()
    return bool(res.data)


async def delete_schedule(schedule_id: str) -> bool:
    """Delete a schedule."""
    res = await supabase.table("report_schedules").delete().eq("id", schedule_id).execute()
    return bool(res.data)


# ── Schedule execution ───────────────────────────────────────────────

async def execute_scheduled_report(schedule_id: str) -> dict[str, Any]:
    """Execute a scheduled report: generate SQL, run, save, push."""
    res = await supabase.table("report_schedules").select("*").eq("id", schedule_id).maybe_single().execute()
    sched = res.data
    if not sched:
        return {"success": False, "error": "Schedule not found"}

    org_id = sched["organization_id"]
    user_id = sched["user_id"]
    nl_query = sched["nl_query"]

    # Generate SQL
    gen = await generate_sql(nl_query, org_id)
    if not gen["success"]:
        await _mark_failure(schedule_id, gen["error"])
        return gen

    sql = gen["sql"]

    # Execute
    exec_result = await execute_report_sql(sql)
    if not exec_result["success"]:
        await _mark_failure(schedule_id, exec_result["error"])
        return exec_result

    data = exec_result["data"]
    chart_config = suggest_chart_config(data)
    summary = await generate_insight(nl_query, data)

    # Save report
    report = await save_report(
        org_id=org_id, user_id=user_id,
        title=f"[定时] {sched['name']}",
        nl_query=nl_query, generated_sql=sql,
        result_data=data, chart_config=chart_config,
        summary=summary, is_public=True,
    )

    # Update schedule
    next_exec = _compute_next_execution(
        sched["schedule_type"], sched["hour"],
        sched.get("day_of_week", 1), sched.get("day_of_month", 1),
    )
    await supabase.table("report_schedules").update({
        "last_executed_at": datetime.now(UTC).isoformat(),
        "next_execution_at": next_exec.isoformat(),
        "last_report_id": report.get("id"),
        "failure_count": 0,
    }).eq("id", schedule_id).execute()

    # Push to recipients
    await _push_to_recipients(sched.get("recipients", []), sched["name"], summary, report.get("id"))

    return {"success": True, "report_id": report.get("id"), "summary": summary}


async def _mark_failure(schedule_id: str, error: str):
    """Increment failure count on schedule."""
    try:
        await supabase.table("report_schedules").update({
            "failure_count": 1,  # simplified: just set to 1 (could increment with RPC)
        }).eq("id", schedule_id).execute()
    except Exception as e:
        logger.error(f"Failed to mark schedule failure: {e}")


async def _push_to_recipients(recipients: list, name: str, summary: str, report_id: str | None):
    """Push report results to recipients (notification only for now)."""
    for r in recipients:
        rtype = r.get("type")
        if rtype == "user_id":
            # Create in-app notification
            try:
                await supabase.table("notifications").insert({
                    "user_id": r["value"],
                    "title": f"定时报表: {name}",
                    "message": summary[:200] if summary else "报表已生成",
                    "type": "report",
                    "metadata": {"report_id": report_id},
                }).execute()
            except Exception as e:
                logger.error(f"Failed to push notification: {e}")
        # email push can be added later via Celery task


# ── Scheduling helpers ───────────────────────────────────────────────

def _compute_next_execution(schedule_type: str, hour: int, day_of_week: int = 1, day_of_month: int = 1) -> datetime:
    """Compute next execution time for a schedule."""
    now = datetime.now(UTC)
    target_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)

    if schedule_type == "daily":
        if target_time <= now:
            target_time += timedelta(days=1)
    elif schedule_type == "weekly":
        days_ahead = day_of_week - now.weekday()
        if days_ahead <= 0 or (days_ahead == 0 and target_time <= now):
            days_ahead += 7
        target_time += timedelta(days=days_ahead)
    elif schedule_type == "monthly":
        if now.day >= day_of_month or (now.day == day_of_month and target_time <= now):
            if now.month == 12:
                target_time = target_time.replace(year=now.year + 1, month=1, day=day_of_month)
            else:
                target_time = target_time.replace(month=now.month + 1, day=day_of_month)
        else:
            target_time = target_time.replace(day=day_of_month)

    return target_time


def _compute_next_execution_after_toggle(active: bool) -> datetime:
    """When reactivating, set next execution to tomorrow at 9am."""
    now = datetime.now(UTC)
    return now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
