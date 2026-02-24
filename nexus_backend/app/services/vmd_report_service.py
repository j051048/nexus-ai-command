"""
VMD Report Service - Auto-generate periodic VMD reports.

Provides:
- Daily report: aggregate today's tasks, clues, compliance checks
- Weekly report: aggregate weekly metrics across all VMD domains
- Overview stats: real-time KPI cards for the frontend VMDCenter dashboard
  (today_tasks, active_agents, new_clues, pending_review)
- Monthly report: comprehensive monthly analysis
- Report export (Markdown / HTML)
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)


class VMDReportService:
    """Auto-generate periodic VMD reports and overview statistics."""

    # ═══════════════════════════════════════════════════════
    #  Overview Stats  (frontend VMDCenter stat cards)
    # ═══════════════════════════════════════════════════════

    async def get_overview_stats(self, tenant_id: str, db=None) -> dict:
        """
        Return real-time overview statistics for the VMDCenter dashboard.

        This is what the frontend stats cards use:
        - today_tasks: tasks created or due today
        - active_agents: distinct agents currently active
        - new_clues: clues created today
        - pending_review: items pending compliance review
        """
        db = db or supabase
        stats = {
            "today_tasks": 0,
            "active_agents": 0,
            "new_clues": 0,
            "pending_review": 0,
        }
        if not db:
            return stats

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        today_start = f"{today}T00:00:00"

        # ── Today's tasks ──────────────────────────────────
        try:
            res = (
                await db.table("vmd_main_task")
                .select("id", count="exact")
                .eq("tenant_id", tenant_id)
                .gte("create_time", today_start)
                .execute()
            )
            stats["today_tasks"] = res.count if res.count is not None else len(res.data or [])
        except Exception as e:
            logger.debug("Failed to count today tasks: %s", e)

        # ── Active agents ──────────────────────────────────
        try:
            res = (
                await db.table("vmd_agent_config")
                .select("id", count="exact")
                .eq("tenant_id", tenant_id)
                .eq("is_active", True)
                .execute()
            )
            stats["active_agents"] = res.count if res.count is not None else len(res.data or [])
        except Exception as e:
            logger.debug("Failed to count active agents: %s", e)

        # ── New clues today ────────────────────────────────
        try:
            res = (
                await db.table("business_clue")
                .select("id", count="exact")
                .eq("tenant_id", tenant_id)
                .gte("create_time", today_start)
                .execute()
            )
            stats["new_clues"] = res.count if res.count is not None else len(res.data or [])
        except Exception as e:
            logger.debug("Failed to count new clues: %s", e)

        # ── Pending compliance review ──────────────────────
        try:
            res = (
                await db.table("bid_project")
                .select("id", count="exact")
                .eq("tenant_id", tenant_id)
                .eq("compliance_status", "unchecked")
                .execute()
            )
            stats["pending_review"] = res.count if res.count is not None else len(res.data or [])
        except Exception as e:
            logger.debug("Failed to count pending reviews: %s", e)

        return stats

    # ═══════════════════════════════════════════════════════
    #  Daily Report
    # ═══════════════════════════════════════════════════════

    async def generate_daily_report(
        self, tenant_id: str, date: str | None = None, db=None
    ) -> dict[str, Any]:
        """
        Generate a daily VMD report.

        Aggregates today's tasks, clues, compliance checks, and bid activity.
        Optionally uses LLM to produce a narrative summary.
        """
        db = db or supabase
        if not date:
            date = datetime.now(UTC).strftime("%Y-%m-%d")

        start_date = f"{date}T00:00:00Z"
        end_date = f"{date}T23:59:59Z"

        # Collect data
        tasks_data = await self._aggregate_tasks(db, tenant_id, start_date, end_date)
        clues_data = await self._aggregate_clues(db, tenant_id, start_date, end_date)
        compliance_data = await self._aggregate_compliance(db, tenant_id, start_date, end_date)
        bids_data = await self._aggregate_bids(db, tenant_id, start_date, end_date)

        # Build narrative summary
        summary = (
            f"日期: {date}\n"
            f"任务: {tasks_data['total']} 个（完成 {tasks_data['completed']}，"
            f"进行中 {tasks_data['in_progress']}，待处理 {tasks_data['pending']}）\n"
            f"新线索: {clues_data['new_count']} 条，已转化 {clues_data['converted_count']} 条\n"
            f"合规检查: {compliance_data['total_checks']} 次，"
            f"通过 {compliance_data['passed']}，拦截 {compliance_data['blocked']}\n"
            f"投标: 新增 {bids_data['new_projects']} 个项目，提交 {bids_data['submitted']} 个"
        )

        # Try LLM-enhanced summary
        report_content = summary
        try:
            from app.services.ai_service import AIService

            prompt = (
                f"基于以下VMD日报数据，生成简洁的日报摘要（中文）：\n\n{summary}\n\n"
                "格式：1.今日概览 2.线索动态 3.合规状况 4.重点事项 5.明日建议"
            )
            report_content = await AIService.call_llm(
                prompt, "你是企业营销运营数据分析师。简洁输出。"
            )
        except Exception as e:
            logger.debug("LLM daily report generation skipped: %s", e)

        report = {
            "report_type": "daily",
            "date": date,
            "tenant_id": tenant_id,
            "data": {
                "tasks": tasks_data,
                "clues": clues_data,
                "compliance": compliance_data,
                "bids": bids_data,
            },
            "content": report_content,
            "generated_at": datetime.now(UTC).isoformat(),
        }

        # Persist
        await self._save_report(db, tenant_id, "daily", date, report)

        logger.info("Daily report generated for tenant %s on %s", tenant_id, date)
        return report

    # ═══════════════════════════════════════════════════════
    #  Weekly Report
    # ═══════════════════════════════════════════════════════

    async def generate_weekly_report(
        self, tenant_id: str, db=None
    ) -> dict[str, Any]:
        """
        Generate a weekly VMD report covering the last 7 days.

        Includes daily breakdown trend data and an LLM-generated narrative.
        """
        db = db or supabase

        now = datetime.now(UTC)
        week_start = (now - timedelta(days=6)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_end = now

        start_iso = week_start.isoformat()
        end_iso = week_end.isoformat()

        # Aggregate full-week data
        tasks_data = await self._aggregate_tasks(db, tenant_id, start_iso, end_iso)
        clues_data = await self._aggregate_clues(db, tenant_id, start_iso, end_iso)
        compliance_data = await self._aggregate_compliance(db, tenant_id, start_iso, end_iso)
        bids_data = await self._aggregate_bids(db, tenant_id, start_iso, end_iso)

        # Daily breakdown for trend charts
        daily_breakdown: list[dict] = []
        for i in range(7):
            day = week_start + timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            day_end = (day + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            ).isoformat()

            day_tasks = await self._aggregate_tasks(db, tenant_id, day_start, day_end)
            day_clues = await self._aggregate_clues(db, tenant_id, day_start, day_end)

            daily_breakdown.append({
                "date": day.strftime("%Y-%m-%d"),
                "tasks_completed": day_tasks.get("completed", 0),
                "new_clues": day_clues.get("new_count", 0),
            })

        # Narrative summary
        summary = (
            f"周期: {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}\n"
            f"任务: {tasks_data['total']} 个（完成 {tasks_data['completed']}）\n"
            f"线索: 新增 {clues_data['new_count']}，转化 {clues_data['converted_count']}\n"
            f"合规: {compliance_data['total_checks']} 次检查\n"
            f"投标: {bids_data['new_projects']} 新项目"
        )

        report_content = summary
        try:
            from app.services.ai_service import AIService

            prompt = (
                f"基于以下VMD周报数据，生成结构化周报（中文）：\n\n{summary}\n\n"
                "格式：1.本周概览 2.线索分析 3.投标进展 4.合规状况 "
                "5.趋势分析 6.问题与风险 7.下周计划"
            )
            report_content = await AIService.call_llm(
                prompt, "你是企业营销运营分析师。突出趋势变化和行动建议。"
            )
        except Exception as e:
            logger.debug("LLM weekly report generation skipped: %s", e)

        report = {
            "report_type": "weekly",
            "tenant_id": tenant_id,
            "week_start": week_start.strftime("%Y-%m-%d"),
            "week_end": week_end.strftime("%Y-%m-%d"),
            "data": {
                "tasks": tasks_data,
                "clues": clues_data,
                "compliance": compliance_data,
                "bids": bids_data,
            },
            "daily_breakdown": daily_breakdown,
            "content": report_content,
            "generated_at": datetime.now(UTC).isoformat(),
        }

        await self._save_report(
            db, tenant_id, "weekly", week_start.strftime("%Y-%m-%d"), report
        )

        logger.info(
            "Weekly report generated for tenant %s (%s ~ %s)",
            tenant_id,
            report["week_start"],
            report["week_end"],
        )
        return report

    # ═══════════════════════════════════════════════════════
    #  Internal Aggregation Helpers
    # ═══════════════════════════════════════════════════════

    async def _aggregate_tasks(
        self, db, tenant_id: str, start: str, end: str
    ) -> dict:
        """Count tasks within [start, end]."""
        result = {"total": 0, "completed": 0, "pending": 0, "in_progress": 0}
        if not db:
            return result

        try:
            res = (
                await db.table("vmd_main_task")
                .select("*")
                .eq("tenant_id", tenant_id)
                .gte("create_time", start)
                .lte("create_time", end)
                .execute()
            )
            tasks = res.data or []
            result["total"] = len(tasks)
            for t in tasks:
                status = t.get("status", "pending")
                if status in ("completed", "done"):
                    result["completed"] += 1
                elif status == "in_progress":
                    result["in_progress"] += 1
                else:
                    result["pending"] += 1
        except Exception as e:
            logger.warning("Failed to aggregate tasks: %s", e)
        return result

    async def _aggregate_clues(
        self, db, tenant_id: str, start: str, end: str
    ) -> dict:
        """Count clues within [start, end]."""
        result: dict[str, Any] = {"new_count": 0, "converted_count": 0, "total_value": 0}
        if not db:
            return result

        try:
            res = (
                await db.table("business_clue")
                .select("*")
                .eq("tenant_id", tenant_id)
                .gte("create_time", start)
                .lte("create_time", end)
                .execute()
            )
            clues = res.data or []
            result["new_count"] = len(clues)
            for c in clues:
                if c.get("status") == "converted":
                    result["converted_count"] += 1
                result["total_value"] += float(c.get("estimated_value", 0) or 0)
            result["total_value"] = round(result["total_value"], 2)
        except Exception as e:
            logger.warning("Failed to aggregate clues: %s", e)
        return result

    async def _aggregate_compliance(
        self, db, tenant_id: str, start: str, end: str
    ) -> dict:
        """Count compliance checks within [start, end]."""
        result = {"total_checks": 0, "passed": 0, "blocked": 0, "has_issues": 0}
        if not db:
            return result

        try:
            res = (
                await db.table("compliance_check_log")
                .select("*")
                .eq("tenant_id", tenant_id)
                .gte("created_at", start)
                .lte("created_at", end)
                .execute()
            )
            logs = res.data or []
            result["total_checks"] = len(logs)
            for log in logs:
                error_count = log.get("error_count", 0) or 0
                warning_count = log.get("warning_count", 0) or 0
                if error_count == 0 and warning_count == 0:
                    result["passed"] += 1
                elif error_count > 0:
                    result["blocked"] += 1
                else:
                    result["has_issues"] += 1
        except Exception as e:
            logger.warning("Failed to aggregate compliance checks: %s", e)
        return result

    async def _aggregate_bids(
        self, db, tenant_id: str, start: str, end: str
    ) -> dict:
        """Count bid projects within [start, end]."""
        result: dict[str, Any] = {
            "new_projects": 0,
            "submitted": 0,
            "won": 0,
            "pipeline_value": 0,
        }
        if not db:
            return result

        try:
            res = (
                await db.table("bid_project")
                .select("*")
                .eq("tenant_id", tenant_id)
                .gte("create_time", start)
                .lte("create_time", end)
                .execute()
            )
            projects = res.data or []
            result["new_projects"] = len(projects)
            for p in projects:
                status = p.get("status", "")
                if status == "submitted":
                    result["submitted"] += 1
                elif status == "won":
                    result["won"] += 1
                est = float(p.get("estimated_value", 0) or 0)
                if status in ("identified", "analyzing", "preparing", "submitted"):
                    result["pipeline_value"] += est
            result["pipeline_value"] = round(result["pipeline_value"], 2)
        except Exception as e:
            logger.warning("Failed to aggregate bid projects: %s", e)
        return result

    async def _save_report(
        self,
        db,
        tenant_id: str,
        report_type: str,
        report_date: str,
        report: dict,
    ) -> None:
        """Persist report to ``vmd_reports`` table."""
        if not db:
            return
        try:
            await db.table("vmd_reports").insert({
                "tenant_id": tenant_id,
                "report_type": report_type,
                "report_date": report_date,
                "report_data": report.get("data", {}),
                "report_content": report.get("content", ""),
                "created_at": report.get("generated_at", datetime.now(UTC).isoformat()),
            }).execute()
        except Exception as e:
            logger.warning("Failed to save %s report to DB: %s", report_type, e)


# Module-level singleton
vmd_report_service = VMDReportService()
