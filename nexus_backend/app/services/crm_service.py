"""
客户关系管理服务 (CRM)

提供客户管理、联系人管理、活动时间线、客户统计等功能。
数据通过 Supabase PostgREST 进行 CRUD 操作，按 organization_id 隔离。
"""

import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# 客户阶段定义
CUSTOMER_STAGES = {
    "lead": {"name": "线索", "order": 1, "color": "#94a3b8"},
    "prospect": {"name": "意向", "order": 2, "color": "#3b82f6"},
    "opportunity": {"name": "商机", "order": 3, "color": "#f59e0b"},
    "customer": {"name": "成交", "order": 4, "color": "#22c55e"},
    "churned": {"name": "流失", "order": 5, "color": "#ef4444"},
}

ACTIVITY_TYPES = {
    "call": {"name": "电话", "icon": "phone"},
    "email": {"name": "邮件", "icon": "mail"},
    "meeting": {"name": "会议", "icon": "calendar"},
    "note": {"name": "备注", "icon": "file-text"},
    "deal_update": {"name": "交易更新", "icon": "trending-up"},
}


class CRMService:
    """客户关系管理服务"""

    # ─── 客户 CRUD ─────────────────────────────────────────

    async def create_customer(self, org_id: str, data: dict, db=None) -> dict:
        """创建客户"""
        customer = {
            "id": str(uuid.uuid4()),
            "organization_id": org_id,
            "name": data.get("name", ""),
            "company": data.get("company", ""),
            "industry": data.get("industry", ""),
            "stage": data.get("stage", "lead"),
            "source": data.get("source", ""),
            "estimated_value": data.get("estimated_value", 0),
            "assigned_to": data.get("assigned_to"),
            "tags": data.get("tags", []),
            "metadata": data.get("metadata", {}),
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        if not customer["name"]:
            raise ValueError("客户名称不能为空")

        if customer["stage"] not in CUSTOMER_STAGES:
            raise ValueError(f"无效的客户阶段: {customer['stage']}")

        if db:
            try:
                insert_data = {
                    "organization_id": org_id,
                    "name": customer["name"],
                    "company": customer["company"],
                    "industry": customer["industry"],
                    "stage": customer["stage"],
                    "source": customer["source"],
                    "estimated_value": customer["estimated_value"],
                    "assigned_to": customer["assigned_to"],
                    "tags": customer["tags"],
                    "metadata": customer["metadata"],
                }
                res = await db.table("customers").insert(insert_data).execute()
                if res.data:
                    customer = {**customer, **res.data[0]}
            except Exception as e:
                logger.error(f"Failed to create customer in DB: {e}")
                raise

        logger.info(f"Customer created: {customer['name']} in org {org_id}")
        return customer

    async def update_customer(self, customer_id: str, data: dict, db=None) -> dict:
        """更新客户信息"""
        allowed_fields = [
            "name", "company", "industry", "stage", "source",
            "estimated_value", "assigned_to", "tags", "metadata",
        ]
        update_data = {k: v for k, v in data.items() if k in allowed_fields}
        update_data["updated_at"] = datetime.now(UTC).isoformat()

        if "stage" in update_data and update_data["stage"] not in CUSTOMER_STAGES:
            raise ValueError(f"无效的客户阶段: {update_data['stage']}")

        if db:
            try:
                res = (
                    await db.table("customers")
                    .update(update_data)
                    .eq("id", customer_id)
                    .execute()
                )
                if res.data:
                    return res.data[0]
            except Exception as e:
                logger.error(f"Failed to update customer: {e}")
                raise
            return {"id": customer_id, **update_data}

        return {"id": customer_id, **update_data}

    async def get_customer(self, customer_id: str, db=None) -> dict | None:
        """获取客户详情"""
        if db:
            try:
                res = (
                    await db.table("customers")
                    .select("*")
                    .eq("id", customer_id)
                    .maybe_single()
                    .execute()
                )
                if res.data:
                    return res.data
                return None
            except Exception as e:
                logger.error(f"Customer query failed: {e}")
                raise

        # 无数据库连接时返回 None
        return None

    async def list_customers(
        self, org_id: str, filters: dict | None = None, db=None
    ) -> list[dict]:
        """列出组织的所有客户，支持筛选"""
        filters = filters or {}

        if db:
            try:
                query = (
                    db.table("customers")
                    .select("*")
                    .eq("organization_id", org_id)
                )

                if filters.get("stage"):
                    query = query.eq("stage", filters["stage"])
                if filters.get("industry"):
                    query = query.eq("industry", filters["industry"])
                if filters.get("assigned_to"):
                    query = query.eq("assigned_to", filters["assigned_to"])

                query = query.order("updated_at", desc=True)

                if filters.get("limit"):
                    query = query.limit(filters["limit"])

                res = await query.execute()
                return res.data or []
            except Exception as e:
                logger.error(f"Customer list query failed: {e}")
                raise

        # 无数据库连接时返回空列表
        return []

    async def search_customers(self, org_id: str, query: str, db=None) -> list[dict]:
        """搜索客户（按名称或公司名）"""
        if not query or len(query.strip()) < 1:
            return []

        if db:
            try:
                res = (
                    await db.table("customers")
                    .select("*")
                    .eq("organization_id", org_id)
                    .or_(f"name.ilike.%{query}%,company.ilike.%{query}%")
                    .order("updated_at", desc=True)
                    .limit(20)
                    .execute()
                )
                return res.data or []
            except Exception as e:
                logger.error(f"Customer search failed: {e}")
                raise

        # 无数据库连接时返回空列表
        return []

    # ─── 联系人管理 ─────────────────────────────────────────

    async def create_contact(self, customer_id: str, data: dict, db=None) -> dict:
        """创建联系人"""
        contact = {
            "id": str(uuid.uuid4()),
            "customer_id": customer_id,
            "name": data.get("name", ""),
            "title": data.get("title", ""),
            "phone": data.get("phone", ""),
            "email": data.get("email", ""),
            "is_primary": data.get("is_primary", False),
            "created_at": datetime.now(UTC).isoformat(),
        }

        if not contact["name"]:
            raise ValueError("联系人姓名不能为空")

        if db:
            try:
                res = (
                    await db.table("customer_contacts")
                    .insert({
                        "customer_id": customer_id,
                        "name": contact["name"],
                        "title": contact["title"],
                        "phone": contact["phone"],
                        "email": contact["email"],
                        "is_primary": contact["is_primary"],
                    })
                    .execute()
                )
                if res.data:
                    contact = {**contact, **res.data[0]}
            except Exception as e:
                logger.error(f"Failed to create contact: {e}")
                raise

        return contact

    async def list_contacts(self, customer_id: str, db=None) -> list[dict]:
        """获取客户的联系人列表"""
        if db:
            try:
                res = (
                    await db.table("customer_contacts")
                    .select("*")
                    .eq("customer_id", customer_id)
                    .order("is_primary", desc=True)
                    .execute()
                )
                return res.data or []
            except Exception as e:
                logger.error(f"Contact list query failed: {e}")
                raise

        # 无数据库连接时返回空列表
        return []

    # ─── 活动时间线 ─────────────────────────────────────────

    async def create_activity(
        self,
        customer_id: str,
        activity_type: str,
        content: str,
        user_id: str,
        db=None,
    ) -> dict:
        """创建客户活动记录"""
        if activity_type not in ACTIVITY_TYPES:
            raise ValueError(f"无效的活动类型: {activity_type}")

        activity = {
            "id": str(uuid.uuid4()),
            "customer_id": customer_id,
            "user_id": user_id,
            "activity_type": activity_type,
            "content": content,
            "metadata": {},
            "created_at": datetime.now(UTC).isoformat(),
        }

        if db:
            try:
                res = (
                    await db.table("customer_activities")
                    .insert({
                        "customer_id": customer_id,
                        "user_id": user_id,
                        "activity_type": activity_type,
                        "content": content,
                    })
                    .execute()
                )
                if res.data:
                    activity = {**activity, **res.data[0]}
            except Exception as e:
                logger.error(f"Failed to create activity: {e}")
                raise

        return activity

    async def get_activity_timeline(
        self, customer_id: str, limit: int = 20, db=None
    ) -> list[dict]:
        """获取客户的活动时间线"""
        if db:
            try:
                res = (
                    await db.table("customer_activities")
                    .select("*")
                    .eq("customer_id", customer_id)
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute()
                )
                return res.data or []
            except Exception as e:
                logger.error(f"Activity timeline query failed: {e}")
                raise

        # 无数据库连接时返回空列表
        return []

    # ─── 客户统计 ──────────────────────────────────────────

    async def get_customer_stats(self, org_id: str, db=None) -> dict:
        """客户统计: 总数、各阶段分布、新增、转化率"""
        customers = await self.list_customers(org_id, db=db)

        total = len(customers)
        stage_counts = defaultdict(int)
        for c in customers:
            stage_counts[c.get("stage", "lead")] += 1

        # 计算本月新增
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        new_this_month = sum(
            1 for c in customers
            if self._parse_datetime(c.get("created_at", "")) >= month_start
        )

        # 转化率: customer / (total - churned)
        active_total = total - stage_counts.get("churned", 0)
        conversion_rate = round(
            stage_counts.get("customer", 0) / max(1, active_total) * 100, 1
        )

        total_value = sum(float(c.get("estimated_value", 0) or 0) for c in customers)

        stage_distribution = []
        for stage_key, stage_info in CUSTOMER_STAGES.items():
            stage_distribution.append({
                "stage": stage_key,
                "name": stage_info["name"],
                "count": stage_counts.get(stage_key, 0),
                "color": stage_info["color"],
            })

        return {
            "total_customers": total,
            "new_this_month": new_this_month,
            "conversion_rate": conversion_rate,
            "total_estimated_value": round(total_value, 2),
            "churned": stage_counts.get("churned", 0),
            "stage_distribution": stage_distribution,
        }

    @staticmethod
    def _parse_datetime(dt_str: str) -> datetime:
        """安全解析日期时间字符串"""
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return datetime.min.replace(tzinfo=UTC)


# Global instance
crm_service = CRMService()
