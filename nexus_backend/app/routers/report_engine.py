"""
Report Engine API Routes
AI-generated SQL reports with scheduling and push delivery.
"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.report_engine_service import (
    create_schedule,
    delete_saved_report,
    delete_schedule,
    execute_report_sql,
    execute_scheduled_report,
    generate_insight,
    generate_sql,
    get_saved_report,
    list_saved_reports,
    list_schedules,
    save_report,
    suggest_chart_config,
    toggle_schedule,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/report-engine", tags=["ReportEngine"])


# ── Ad-hoc report generation ─────────────────────────────────────────


class GenerateReportRequest(BaseModel):
    nl_query: str
    title: str | None = None


@router.post("/generate")
async def generate_report(
    body: GenerateReportRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Generate a report from natural language query (NL -> SQL -> execute -> insight)."""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

    # Generate SQL
    gen = await generate_sql(body.nl_query, org_id)
    if not gen["success"]:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, gen["error"])

    # Execute
    exec_result = await execute_report_sql(gen["sql"])
    if not exec_result["success"]:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, exec_result["error"])

    data = exec_result["data"]
    chart_config = suggest_chart_config(data)
    summary = await generate_insight(body.nl_query, data)

    return api_success(
        data={
            "sql": gen["sql"],
            "result": data,
            "total_rows": exec_result["total_rows"],
            "chart_config": chart_config,
            "summary": summary,
        }
    )


@router.post("/generate-sql")
async def generate_sql_only(
    body: GenerateReportRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Generate SQL from natural language without executing."""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

    gen = await generate_sql(body.nl_query, org_id)
    if not gen["success"]:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, gen["error"])

    return api_success(data={"sql": gen["sql"]})


# ── Saved reports ────────────────────────────────────────────────────


class SaveReportRequest(BaseModel):
    title: str
    nl_query: str
    generated_sql: str
    result_data: list
    chart_config: dict = {}
    summary: str | None = None
    is_public: bool = False


@router.post("/save")
async def save_generated_report(
    body: SaveReportRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Save a generated report."""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

    report = await save_report(
        org_id=org_id,
        user_id=user_id,
        title=body.title,
        nl_query=body.nl_query,
        generated_sql=body.generated_sql,
        result_data=body.result_data,
        chart_config=body.chart_config,
        summary=body.summary,
        is_public=body.is_public,
    )
    return api_success(data=report, message="报表已保存")


@router.get("/saved")
async def get_saved_reports(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    limit: int = 20,
):
    """List saved reports (own + public in org)."""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

    reports = await list_saved_reports(org_id, user_id, limit)
    return api_success(data=reports)


@router.get("/saved/{report_id}")
async def get_report_detail(
    report_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get a single saved report with full data."""
    report = await get_saved_report(report_id)
    if not report:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "报表不存在")
    return api_success(data=report)


@router.delete("/saved/{report_id}")
async def delete_report(
    report_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a saved report (owner only)."""
    ok = await delete_saved_report(report_id, user_id)
    if not ok:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "报表不存在或无权删除")
    return api_success(data={}, message="报表已删除")


# ── Report schedules ─────────────────────────────────────────────────


class CreateScheduleRequest(BaseModel):
    name: str
    nl_query: str
    schedule_type: str = "daily"
    hour: int = 9
    day_of_week: int = 1
    day_of_month: int = 1
    recipients: list = []
    output_format: str = "both"


@router.post("/schedules")
async def create_report_schedule(
    body: CreateScheduleRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Create a scheduled report."""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

    sched = await create_schedule(
        org_id=org_id,
        user_id=user_id,
        name=body.name,
        nl_query=body.nl_query,
        schedule_type=body.schedule_type,
        hour=body.hour,
        day_of_week=body.day_of_week,
        day_of_month=body.day_of_month,
        recipients=body.recipients,
        output_format=body.output_format,
    )
    return api_success(data=sched, message="定时报表已创建")


@router.get("/schedules")
async def get_report_schedules(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """List all report schedules for org."""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

    schedules = await list_schedules(org_id)
    return api_success(data=schedules)


@router.put("/schedules/{schedule_id}/toggle")
async def toggle_report_schedule(
    schedule_id: str,
    active: bool,
    user_id: str = Depends(get_current_user_id),
):
    """Toggle a schedule active/inactive."""
    ok = await toggle_schedule(schedule_id, active)
    if not ok:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "定时报表不存在")
    return api_success(data={}, message=f"定时报表已{'启用' if active else '禁用'}")


@router.delete("/schedules/{schedule_id}")
async def delete_report_schedule(
    schedule_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a schedule."""
    ok = await delete_schedule(schedule_id)
    if not ok:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "定时报表不存在")
    return api_success(data={}, message="定时报表已删除")


@router.post("/schedules/{schedule_id}/run")
async def run_report_schedule(
    schedule_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Manually trigger a scheduled report execution."""
    result = await execute_scheduled_report(schedule_id)
    if not result.get("success"):
        raise api_error(
            ErrorCode.SYSTEM_INTERNAL_ERROR, result.get("error", "执行失败")
        )
    return api_success(data=result, message="定时报表已执行")
