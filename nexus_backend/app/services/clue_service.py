"""
商机线索管理服务 (Clue/Lead Service)

线索全生命周期管理:
- 线索 CRUD（自动生成 CLUE-YYYYMMDD-XXXX 编码）
- 跟进记录
- 线索转客户
- AI 自动评级
- 统计分析（按状态 / 来源 / 优先级）
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

CLUE_SOURCES = {
    "website": "官网",
    "exhibition": "展会",
    "referral": "转介绍",
    "cold_call": "电话开发",
    "academic": "学术线索",
    "tender": "招标信息",
    "social_media": "社交媒体",
    "partner": "渠道合作",
    "other": "其他",
}

CLUE_LEVELS = {
    "A": {"name": "高价值", "description": "有明确需求和预算，近期采购", "color": "#22c55e"},
    "B": {"name": "中高价值", "description": "有需求，预算待确认，3个月内可能采购", "color": "#3b82f6"},
    "C": {"name": "中等价值", "description": "有潜在需求，需要持续培育", "color": "#f59e0b"},
    "D": {"name": "低价值", "description": "需求不明确，仅作信息储备", "color": "#94a3b8"},
}

CLUE_STATUSES = {
    "new": "新线索",
    "contacted": "已联系",
    "following": "跟进中",
    "qualified": "已确认",
    "converted": "已转化",
    "lost": "已流失",
    "invalid": "无效",
}

CLUE_PRIORITIES = {
    "high": "高",
    "medium": "中",
    "low": "低",
}


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _generate_clue_code() -> str:
    """Generate a human-readable clue code like ``CLUE-20260224-8A3F``."""
    date_part = datetime.now(UTC).strftime("%Y%m%d")
    rand_part = f"{random.randint(0, 0xFFFF):04X}"
    return f"CLUE-{date_part}-{rand_part}"


# ═══════════════════════════════════════════════════════════════════════════════
#  Service
# ═══════════════════════════════════════════════════════════════════════════════


class ClueService:
    """商机线索全生命周期管理服务"""

    # ─── CRUD ──────────────────────────────────────────────

    async def create_clue(
        self,
        tenant_id: str,
        data: dict,
        user_id: str | None = None,
        db=None,
    ) -> dict:
        """
        Create a new business clue.

        Auto-generates ``clue_code`` in the format ``CLUE-YYYYMMDD-XXXX``.
        """
        db = db or supabase
        if not db:
            raise RuntimeError("Database not available")

        now = datetime.now(UTC).isoformat()
        clue = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "clue_code": data.get("clue_code") or _generate_clue_code(),
            "title": data.get("title", ""),
            "company": data.get("company", ""),
            "contact_name": data.get("contact_name", ""),
            "contact_phone": data.get("contact_phone", ""),
            "contact_email": data.get("contact_email", ""),
            "source": data.get("source", "other"),
            "level": data.get("level", "C"),
            "priority": data.get("priority", "medium"),
            "status": data.get("status", "new"),
            "estimated_value": data.get("estimated_value", 0),
            "product_interest": data.get("product_interest", ""),
            "description": data.get("description", ""),
            "assigned_to": data.get("assigned_to"),
            "created_by": user_id,
            "metadata": data.get("metadata", {}),
            "create_time": now,
            "update_time": now,
        }

        if not clue["title"]:
            raise ValueError("线索标题不能为空")

        if clue["source"] not in CLUE_SOURCES:
            clue["source"] = "other"
        if clue["level"] not in CLUE_LEVELS:
            clue["level"] = "C"

        try:
            insert_data = {k: v for k, v in clue.items() if k != "id"}
            res = await db.table("business_clue").insert(insert_data).execute()
            if res.data:
                clue = {**clue, **res.data[0]}
            logger.info("Clue created: %s (%s)", clue["clue_code"], clue["title"])
        except Exception as e:
            logger.error("Failed to create clue in DB: %s", e)
            raise

        return clue

    async def list_clues(
        self,
        tenant_id: str,
        filters: dict | None = None,
        page: int = 1,
        page_size: int = 20,
        db=None,
    ) -> dict:
        """
        List clues with filtering and pagination.

        Returns:
            dict with 'items' and 'total' keys
        """
        db = db or supabase
        if not db:
            return {"items": [], "total": 0}

        filters = filters or {}

        try:
            query = (
                db.table("business_clue")
                .select("*", count="exact")
                .eq("tenant_id", tenant_id)
                .order("create_time", desc=True)
            )

            if filters.get("status"):
                query = query.eq("status", filters["status"])
            if filters.get("level"):
                query = query.eq("level", filters["level"])
            if filters.get("source"):
                query = query.eq("source", filters["source"])
            if filters.get("priority"):
                query = query.eq("priority", filters["priority"])
            if filters.get("assigned_to"):
                query = query.eq("assigned_to", filters["assigned_to"])
            if filters.get("search"):
                query = query.or_(
                    f"title.ilike.%{filters['search']}%,"
                    f"company.ilike.%{filters['search']}%,"
                    f"contact_name.ilike.%{filters['search']}%"
                )

            offset = (page - 1) * page_size
            query = query.range(offset, offset + page_size - 1)

            res = await query.execute()
            total = res.count if res.count is not None else 0
            return {"items": res.data or [], "total": total}

        except Exception as e:
            logger.error("Failed to list clues: %s", e)
            return {"items": [], "total": 0}

    async def get_clue(self, clue_id: str, db=None, tenant_id: str | None = None) -> dict | None:
        """Get a single clue by ID."""
        db = db or supabase
        if not db:
            return None

        try:
            res = (
                await db.table("business_clue")
                .select("*")
                .eq("id", clue_id)
                .maybe_single()
                .execute()
            )
            return res.data
        except Exception as e:
            logger.error("Failed to get clue %s: %s", clue_id, e)
            return None

    async def update_clue(
        self,
        clue_id: str,
        data: dict,
        user_id: str | None = None,
        db=None,
        *,
        tenant_id: str | None = None,
    ) -> dict | None:
        """Update a clue."""
        db = db or supabase
        if not db:
            return None

        data["update_time"] = datetime.now(UTC).isoformat()
        if user_id:
            data["updated_by"] = user_id

        # Validate enum fields if present
        if "source" in data and data["source"] not in CLUE_SOURCES:
            raise ValueError(f"无效的线索来源: {data['source']}")
        if "level" in data and data["level"] not in CLUE_LEVELS:
            raise ValueError(f"无效的线索级别: {data['level']}")
        if "status" in data and data["status"] not in CLUE_STATUSES:
            raise ValueError(f"无效的线索状态: {data['status']}")

        try:
            res = (
                await db.table("business_clue")
                .update(data)
                .eq("id", clue_id)
                .execute()
            )
            return res.data[0] if res.data else None
        except Exception as e:
            logger.error("Failed to update clue %s: %s", clue_id, e)
            raise

    # ─── Follow-Up ─────────────────────────────────────────

    async def add_follow_up(
        self,
        clue_id: str,
        user_id: str,
        action: str | None = None,
        content: str | None = None,
        next_action: str | None = None,
        next_action_date: str | None = None,
        db=None,
        *,
        tenant_id: str | None = None,
        data: dict | None = None,
    ) -> dict:
        """
        Add a follow-up record to a clue and advance its status to 'following'.
        """
        db = db or supabase
        if not db:
            raise RuntimeError("Database not available")

        # Support dict-based call from router
        if data:
            action = action or data.get("follow_type", data.get("action", ""))
            content = content or data.get("content", "")
            next_action = next_action or data.get("next_action")
            next_action_date = next_action_date or data.get("next_action_date")

        now = datetime.now(UTC).isoformat()
        follow_up = {
            "clue_id": clue_id,
            "user_id": user_id,
            "action": action or "",
            "content": content or "",
            "next_action": next_action or "",
            "next_action_date": next_action_date,
            "created_at": now,
        }

        try:
            res = await db.table("clue_follow_up").insert(follow_up).execute()

            # Move clue to 'following' status
            await (
                db.table("business_clue")
                .update({"status": "following", "update_time": now})
                .eq("id", clue_id)
                .execute()
            )

            logger.info("Follow-up added for clue %s by user %s", clue_id, user_id)
            return res.data[0] if res.data else follow_up

        except Exception as e:
            logger.error("Failed to add follow-up for clue %s: %s", clue_id, e)
            raise

    # ─── Convert to Customer ───────────────────────────────

    async def convert_to_customer(
        self,
        clue_id: str,
        user_id: str | None = None,
        db=None,
    ) -> dict:
        """
        Convert a clue into a CRM customer record.

        Creates a customer row from the clue data and marks the clue as converted.
        """
        db = db or supabase
        if not db:
            raise RuntimeError("Database not available")

        clue = await self.get_clue(clue_id, db=db)
        if not clue:
            raise ValueError(f"线索不存在: {clue_id}")
        if clue.get("status") == "converted":
            raise ValueError("该线索已经转化为客户")

        customer_data = {
            "organization_id": clue.get("tenant_id"),
            "name": clue.get("contact_name") or clue.get("title", ""),
            "company": clue.get("company", ""),
            "stage": "lead",
            "source": CLUE_SOURCES.get(clue.get("source", ""), clue.get("source", "")),
            "estimated_value": clue.get("estimated_value", 0),
            "assigned_to": clue.get("assigned_to"),
            "metadata": {"converted_from_clue": clue_id, "converted_by": user_id},
        }

        try:
            cust_res = await db.table("customers").insert(customer_data).execute()
            customer = cust_res.data[0] if cust_res.data else customer_data

            # Mark clue as converted
            await (
                db.table("business_clue")
                .update({
                    "status": "converted",
                    "update_time": datetime.now(UTC).isoformat(),
                    "metadata": {
                        **(clue.get("metadata") or {}),
                        "converted_customer_id": customer.get("id"),
                    },
                })
                .eq("id", clue_id)
                .execute()
            )

            logger.info("Clue %s converted to customer %s", clue_id, customer.get("id"))
            return customer

        except Exception as e:
            logger.error("Failed to convert clue %s to customer: %s", clue_id, e)
            raise

    # ─── Statistics ─────────────────────────────────────────

    async def get_clue_stats(self, tenant_id: str, db=None) -> dict:
        """
        Aggregate clue statistics.

        Returns counts grouped by status, source, and priority,
        plus total estimated value and conversion rate.
        """
        db = db or supabase
        if not db:
            return {}

        try:
            res = (
                await db.table("business_clue")
                .select("*")
                .eq("tenant_id", tenant_id)
                .execute()
            )
            clues = res.data or []

            if not clues:
                return {
                    "total": 0,
                    "by_status": {},
                    "by_source": {},
                    "by_priority": {},
                    "conversion_rate": 0,
                    "total_estimated_value": 0,
                }

            by_status: dict[str, int] = {}
            by_source: dict[str, int] = {}
            by_priority: dict[str, int] = {}
            total_value = 0.0
            converted_count = 0

            for clue in clues:
                status = clue.get("status", "new")
                by_status[status] = by_status.get(status, 0) + 1

                source = clue.get("source", "other")
                by_source[source] = by_source.get(source, 0) + 1

                priority = clue.get("priority", "medium")
                by_priority[priority] = by_priority.get(priority, 0) + 1

                total_value += float(clue.get("estimated_value", 0) or 0)
                if status == "converted":
                    converted_count += 1

            total = len(clues)
            conversion_rate = round(converted_count / total * 100, 1) if total > 0 else 0

            return {
                "total": total,
                "by_status": by_status,
                "by_source": by_source,
                "by_priority": by_priority,
                "conversion_rate": conversion_rate,
                "converted_count": converted_count,
                "total_estimated_value": round(total_value, 2),
            }

        except Exception as e:
            logger.error("Failed to get clue stats: %s", e)
            return {}


# Module-level singleton
clue_service = ClueService()
