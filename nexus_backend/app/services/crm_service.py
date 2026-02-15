"""
客户关系管理服务 (CRM)

提供客户管理、联系人管理、活动时间线、客户统计等功能。
数据通过 Supabase PostgREST 进行 CRUD 操作，按 organization_id 隔离。
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

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

    async def create_customer(self, org_id: str, data: Dict, db=None) -> Dict:
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
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
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

    async def update_customer(self, customer_id: str, data: Dict, db=None) -> Dict:
        """更新客户信息"""
        allowed_fields = [
            "name", "company", "industry", "stage", "source",
            "estimated_value", "assigned_to", "tags", "metadata",
        ]
        update_data = {k: v for k, v in data.items() if k in allowed_fields}
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

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

    async def get_customer(self, customer_id: str, db=None) -> Optional[Dict]:
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

        # 无数据库连接时返回 mock
        return self._mock_single_customer(customer_id)

    async def list_customers(
        self, org_id: str, filters: Optional[Dict] = None, db=None
    ) -> List[Dict]:
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

        # 无数据库连接时返回 mock
        return self._mock_customer_list(org_id, filters)

    async def search_customers(self, org_id: str, query: str, db=None) -> List[Dict]:
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

        # 无数据库连接时使用 mock
        all_customers = self._mock_customer_list(org_id)
        return [
            c for c in all_customers
            if query.lower() in (c.get("name", "") + c.get("company", "")).lower()
        ]

    # ─── 联系人管理 ─────────────────────────────────────────

    async def create_contact(self, customer_id: str, data: Dict, db=None) -> Dict:
        """创建联系人"""
        contact = {
            "id": str(uuid.uuid4()),
            "customer_id": customer_id,
            "name": data.get("name", ""),
            "title": data.get("title", ""),
            "phone": data.get("phone", ""),
            "email": data.get("email", ""),
            "is_primary": data.get("is_primary", False),
            "created_at": datetime.now(timezone.utc).isoformat(),
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

    async def list_contacts(self, customer_id: str, db=None) -> List[Dict]:
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

        # 无数据库连接时返回 mock
        return [
            {
                "id": str(uuid.uuid4()),
                "customer_id": customer_id,
                "name": "张经理",
                "title": "采购部经理",
                "phone": "138****1234",
                "email": "zhang@example.com",
                "is_primary": True,
            },
            {
                "id": str(uuid.uuid4()),
                "customer_id": customer_id,
                "name": "李工",
                "title": "技术部工程师",
                "phone": "139****5678",
                "email": "li@example.com",
                "is_primary": False,
            },
        ]

    # ─── 活动时间线 ─────────────────────────────────────────

    async def create_activity(
        self,
        customer_id: str,
        activity_type: str,
        content: str,
        user_id: str,
        db=None,
    ) -> Dict:
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
            "created_at": datetime.now(timezone.utc).isoformat(),
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
    ) -> List[Dict]:
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

        # 无数据库连接时返回 mock
        import random
        activities = []
        types = list(ACTIVITY_TYPES.keys())
        contents = {
            "call": ["跟进项目进度", "确认需求细节", "讨论报价方案"],
            "email": ["发送产品资料", "确认合同条款", "发送技术方案"],
            "meeting": ["项目需求评审会", "技术方案讨论", "商务谈判"],
            "note": ["客户对价格敏感", "需要定制化方案", "决策周期较长"],
            "deal_update": ["预估金额更新", "阶段推进至商机", "合同签署完成"],
        }
        for i in range(min(limit, 8)):
            act_type = random.choice(types)
            activities.append({
                "id": str(uuid.uuid4()),
                "customer_id": customer_id,
                "user_id": "mock-user",
                "activity_type": act_type,
                "content": random.choice(contents[act_type]),
                "created_at": (
                    datetime.now(timezone.utc) - timedelta(days=random.randint(0, 30))
                ).isoformat(),
            })
        return sorted(activities, key=lambda x: x["created_at"], reverse=True)

    # ─── 客户统计 ──────────────────────────────────────────

    async def get_customer_stats(self, org_id: str, db=None) -> Dict:
        """客户统计: 总数、各阶段分布、新增、转化率"""
        customers = await self.list_customers(org_id, db=db)

        total = len(customers)
        stage_counts = defaultdict(int)
        for c in customers:
            stage_counts[c.get("stage", "lead")] += 1

        # 计算本月新增
        now = datetime.now(timezone.utc)
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

    # ─── Mock 数据 ─────────────────────────────────────────

    @staticmethod
    def _mock_customer_list(org_id: str, filters: Optional[Dict] = None) -> List[Dict]:
        """生成模拟客户数据"""
        import random
        filters = filters or {}

        mock_customers = [
            {"name": "华为云项目", "company": "华为技术有限公司", "industry": "科技", "stage": "customer", "value": 500000},
            {"name": "阿里健康", "company": "阿里巴巴集团", "industry": "医疗", "stage": "opportunity", "value": 300000},
            {"name": "中建三局智能化", "company": "中国建筑第三工程局", "industry": "建筑", "stage": "prospect", "value": 800000},
            {"name": "平安银行数字化", "company": "平安银行", "industry": "金融", "stage": "opportunity", "value": 1200000},
            {"name": "比亚迪供应链", "company": "比亚迪股份有限公司", "industry": "制造", "stage": "lead", "value": 250000},
            {"name": "字节跳动内部工具", "company": "北京字节跳动科技有限公司", "industry": "科技", "stage": "customer", "value": 450000},
            {"name": "万科物业管理", "company": "万科企业股份有限公司", "industry": "地产", "stage": "lead", "value": 180000},
            {"name": "中国移动AI客服", "company": "中国移动通信集团", "industry": "通信", "stage": "prospect", "value": 900000},
            {"name": "美的智能工厂", "company": "美的集团股份有限公司", "industry": "制造", "stage": "churned", "value": 350000},
            {"name": "海尔智家平台", "company": "海尔智家股份有限公司", "industry": "制造", "stage": "opportunity", "value": 420000},
        ]

        customers = []
        for i, mc in enumerate(mock_customers):
            customer = {
                "id": f"mock-customer-{i}",
                "organization_id": org_id,
                "name": mc["name"],
                "company": mc["company"],
                "industry": mc["industry"],
                "stage": mc["stage"],
                "source": random.choice(["网站", "转介绍", "展会", "cold_call"]),
                "estimated_value": mc["value"],
                "assigned_to": None,
                "tags": [],
                "metadata": {},
                "created_at": (
                    datetime.now(timezone.utc) - timedelta(days=random.randint(5, 90))
                ).isoformat(),
                "updated_at": (
                    datetime.now(timezone.utc) - timedelta(days=random.randint(0, 10))
                ).isoformat(),
            }
            customers.append(customer)

        # 应用筛选
        if filters.get("stage"):
            customers = [c for c in customers if c["stage"] == filters["stage"]]

        return customers

    @staticmethod
    def _mock_single_customer(customer_id: str) -> Dict:
        """生成单个模拟客户"""
        return {
            "id": customer_id,
            "organization_id": "default",
            "name": "示例客户",
            "company": "示例科技有限公司",
            "industry": "科技",
            "stage": "opportunity",
            "source": "网站",
            "estimated_value": 100000,
            "assigned_to": None,
            "tags": ["重点客户"],
            "metadata": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _parse_datetime(dt_str: str) -> datetime:
        """安全解析日期时间字符串"""
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return datetime.min.replace(tzinfo=timezone.utc)


# Global instance
crm_service = CRMService()
