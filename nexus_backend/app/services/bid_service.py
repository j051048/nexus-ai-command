"""
投标项目管理服务 (Bid/Tender Service)

投标项目全生命周期管理:
- 项目 CRUD（自动生成 BID-YYYYMMDD-XXXX 编码）
- 合规状态更新
- 投标日历（按截止日期查询）
- AI 招标文件分析
- 统计分析（中标率、管线金额等）
"""

import logging
import random
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════════════════

BID_PROJECT_STATUSES = {
    "identified": "已发现",
    "analyzing": "分析中",
    "preparing": "准备中",
    "submitted": "已投标",
    "won": "已中标",
    "lost": "未中标",
    "cancelled": "已取消",
}

COMPLIANCE_STATUSES = {
    "pending": "待检查",
    "passed": "已通过",
    "has_issues": "有问题",
    "blocked": "不合规",
}


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _generate_project_code() -> str:
    """Generate a human-readable bid-project code like ``BID-20260224-3E7A``."""
    date_part = datetime.now(UTC).strftime("%Y%m%d")
    rand_part = f"{random.randint(0, 0xFFFF):04X}"
    return f"BID-{date_part}-{rand_part}"


# ═══════════════════════════════════════════════════════════════════════════════
#  Service
# ═══════════════════════════════════════════════════════════════════════════════


class BidService:
    """投标项目管理服务"""

    # ─── CRUD ──────────────────────────────────────────────

    async def create_project(
        self,
        tenant_id: str,
        data: dict,
        user_id: str | None = None,
        db=None,
    ) -> dict:
        """
        Create a new bid project.

        Auto-generates ``project_code`` in the format ``BID-YYYYMMDD-XXXX``.
        """
        db = db or supabase
        if not db:
            raise RuntimeError("Database not available")

        now = datetime.now(UTC).isoformat()
        project = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "project_code": data.get("project_code") or _generate_project_code(),
            "title": data.get("title", ""),
            "tender_number": data.get("tender_number", ""),
            "buyer_name": data.get("buyer_name", ""),
            "buyer_contact": data.get("buyer_contact", ""),
            "estimated_value": data.get("estimated_value", 0),
            "status": data.get("status", "identified"),
            "compliance_status": data.get("compliance_status", "pending"),
            "deadline": data.get("deadline"),
            "bid_opening_date": data.get("bid_opening_date"),
            "our_products": data.get("our_products", ""),
            "competitors": data.get("competitors", ""),
            "win_probability": data.get("win_probability", 0),
            "assigned_to": data.get("assigned_to"),
            "created_by": user_id,
            "notes": data.get("notes", ""),
            "metadata": data.get("metadata", {}),
            "create_time": now,
            "update_time": now,
        }

        if not project["title"]:
            raise ValueError("项目标题不能为空")

        if project["status"] not in BID_PROJECT_STATUSES:
            project["status"] = "identified"

        try:
            insert_data = {k: v for k, v in project.items() if k != "id"}
            res = await db.table("bid_project").insert(insert_data).execute()
            if res.data:
                project = {**project, **res.data[0]}
            logger.info(
                "Bid project created: %s (%s)", project["project_code"], project["title"]
            )
        except Exception as e:
            logger.error("Failed to create bid project: %s", e)
            raise

        return project

    async def list_projects(
        self,
        tenant_id: str,
        filters: dict | None = None,
        page: int = 1,
        page_size: int = 20,
        db=None,
    ) -> tuple[list, int]:
        """
        List bid projects with filtering and pagination.

        Returns:
            (items, total_count)
        """
        db = db or supabase
        if not db:
            return [], 0

        filters = filters or {}

        try:
            query = (
                db.table("bid_project")
                .select("*", count="exact")
                .eq("tenant_id", tenant_id)
                .order("create_time", desc=True)
            )

            if filters.get("status"):
                query = query.eq("status", filters["status"])
            if filters.get("compliance_status"):
                query = query.eq("compliance_status", filters["compliance_status"])
            if filters.get("assigned_to"):
                query = query.eq("assigned_to", filters["assigned_to"])
            if filters.get("search"):
                query = query.or_(
                    f"title.ilike.%{filters['search']}%,"
                    f"buyer_name.ilike.%{filters['search']}%,"
                    f"tender_number.ilike.%{filters['search']}%"
                )

            offset = (page - 1) * page_size
            query = query.range(offset, offset + page_size - 1)

            res = await query.execute()
            total = res.count if res.count is not None else 0
            return res.data or [], total

        except Exception as e:
            logger.error("Failed to list bid projects: %s", e)
            return [], 0

    async def get_project(self, project_id: str, db=None) -> dict | None:
        """Get a single bid project by ID."""
        db = db or supabase
        if not db:
            return None

        try:
            res = (
                await db.table("bid_project")
                .select("*")
                .eq("id", project_id)
                .maybe_single()
                .execute()
            )
            return res.data
        except Exception as e:
            logger.error("Failed to get bid project %s: %s", project_id, e)
            return None

    async def update_project(
        self,
        project_id: str,
        data: dict,
        user_id: str | None = None,
        db=None,
    ) -> dict | None:
        """Update a bid project."""
        db = db or supabase
        if not db:
            return None

        data["update_time"] = datetime.now(UTC).isoformat()
        if user_id:
            data["updated_by"] = user_id

        if "status" in data and data["status"] not in BID_PROJECT_STATUSES:
            raise ValueError(f"无效的项目状态: {data['status']}")

        try:
            res = (
                await db.table("bid_project")
                .update(data)
                .eq("id", project_id)
                .execute()
            )
            return res.data[0] if res.data else None
        except Exception as e:
            logger.error("Failed to update bid project %s: %s", project_id, e)
            raise

    # ─── Compliance Status ─────────────────────────────────

    async def update_compliance_status(
        self,
        project_id: str,
        status: str,
        db=None,
    ) -> dict:
        """
        Update the compliance-check status of a bid project.

        Valid statuses: pending, passed, has_issues, blocked
        """
        db = db or supabase
        if not db:
            raise RuntimeError("Database not available")

        if status not in COMPLIANCE_STATUSES:
            raise ValueError(f"无效的合规状态: {status}")

        try:
            res = (
                await db.table("bid_project")
                .update({
                    "compliance_status": status,
                    "update_time": datetime.now(UTC).isoformat(),
                })
                .eq("id", project_id)
                .execute()
            )
            logger.info("Bid project %s compliance status -> %s", project_id, status)
            return res.data[0] if res.data else {"id": project_id, "compliance_status": status}
        except Exception as e:
            logger.error("Failed to update compliance status for %s: %s", project_id, e)
            raise

    # ─── Bid Calendar ──────────────────────────────────────

    async def get_bid_calendar(
        self,
        tenant_id: str,
        start_date: str,
        end_date: str,
        db=None,
    ) -> list:
        """
        Return bid projects whose deadlines fall within ``[start_date, end_date]``.

        Useful for rendering a calendar view of upcoming bid deadlines.
        """
        db = db or supabase
        if not db:
            return []

        try:
            res = (
                await db.table("bid_project")
                .select("*")
                .eq("tenant_id", tenant_id)
                .gte("deadline", start_date)
                .lte("deadline", end_date)
                .order("deadline", desc=False)
                .execute()
            )
            return res.data or []
        except Exception as e:
            logger.error("Failed to get bid calendar: %s", e)
            return []

    # ─── AI Tender Analysis ────────────────────────────────

    async def analyze_tender(
        self,
        tenant_id: str,
        project_id: str,
        content: str,
        db=None,
    ) -> dict[str, Any]:
        """
        AI-analyze a tender document: extract requirements, evaluate win probability.
        """
        if not content or not content.strip():
            raise ValueError("招标文件内容不能为空")

        project = await self.get_project(project_id, db=db)
        project_context = ""
        if project:
            project_context = (
                f"\n## 项目信息\n"
                f"- 项目名称: {project.get('title', '')}\n"
                f"- 采购方: {project.get('buyer_name', '')}\n"
                f"- 我方产品: {project.get('our_products', '')}\n"
                f"- 已知竞品: {project.get('competitors', '')}\n"
            )

        prompt = (
            f"请深度分析以下招标文件：\n\n"
            f"## 招标文件内容\n{content[:6000]}\n"
            f"{project_context}\n\n"
            f"请按以下JSON结构输出：\n"
            f'{{"key_requirements": [...], "qualification_requirements": [...], '
            f'"technical_highlights": [...], "our_advantages": [...], "our_risks": [...], '
            f'"scoring_criteria": {{}}, "win_probability": 60, "key_dates": {{}}, '
            f'"recommended_actions": [...], "overall_assessment": "..."}}'
        )

        try:
            import json

            from app.services.ai_service import AIService

            result = await AIService.call_llm(
                prompt,
                "你是科学仪器行业投标分析专家。输出有效JSON。",
            )
            result = result.strip()
            if result.startswith("```"):
                lines = result.split("\n")
                result = "\n".join(lines[1:-1]).strip()

            try:
                analysis = json.loads(result)
            except json.JSONDecodeError:
                analysis = {"overall_assessment": result, "parse_error": "LLM输出未能解析为JSON"}

            # Persist analysis to project metadata
            if project_id and db and project:
                try:
                    await self.update_project(
                        project_id,
                        {
                            "metadata": {
                                **(project.get("metadata") or {}),
                                "tender_analysis": analysis,
                                "analyzed_at": datetime.now(UTC).isoformat(),
                            },
                            **(
                                {"win_probability": analysis["win_probability"]}
                                if isinstance(analysis.get("win_probability"), int | float)
                                else {}
                            ),
                        },
                        db=db,
                    )
                except Exception as e:
                    logger.warning("Failed to save analysis to project: %s", e)

            return analysis
        except Exception as e:
            logger.error("Failed to analyze tender: %s", e)
            raise

    # ─── Statistics ─────────────────────────────────────────

    async def get_bid_stats(self, tenant_id: str, db=None) -> dict:
        """
        Aggregate bid statistics: win rate, pipeline value, status distribution.
        """
        db = db or supabase
        if not db:
            return {}

        try:
            res = (
                await db.table("bid_project")
                .select("*")
                .eq("tenant_id", tenant_id)
                .execute()
            )
            projects = res.data or []

            if not projects:
                return {
                    "total": 0,
                    "by_status": {},
                    "win_rate": 0,
                    "pipeline_value": 0,
                    "total_won_value": 0,
                }

            by_status: dict[str, int] = {}
            pipeline_value = 0.0
            won_value = 0.0
            won_count = 0
            decided_count = 0  # won + lost

            for p in projects:
                status = p.get("status", "identified")
                by_status[status] = by_status.get(status, 0) + 1

                est = float(p.get("estimated_value", 0) or 0)

                # Pipeline = projects still in play (not won/lost/cancelled)
                if status in ("identified", "analyzing", "preparing", "submitted"):
                    pipeline_value += est

                if status == "won":
                    won_count += 1
                    won_value += est
                    decided_count += 1
                elif status == "lost":
                    decided_count += 1

            win_rate = round(won_count / decided_count * 100, 1) if decided_count > 0 else 0

            return {
                "total": len(projects),
                "by_status": by_status,
                "win_rate": win_rate,
                "won_count": won_count,
                "pipeline_value": round(pipeline_value, 2),
                "total_won_value": round(won_value, 2),
            }

        except Exception as e:
            logger.error("Failed to get bid stats: %s", e)
            return {}


# Module-level singleton
bid_service = BidService()
