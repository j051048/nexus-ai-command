"""
合同生命周期管理服务

提供:
- 合同 CRUD
- 即将到期合同查询
- 合同统计
- 合同事件时间线
"""

import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class ContractService:
    """合同生命周期管理服务"""

    # 合同类型映射
    CONTRACT_TYPES = {
        "sales": "销售合同",
        "purchase": "采购合同",
        "service": "服务合同",
        "nda": "保密协议",
        "other": "其他",
    }

    # 合同状态映射
    CONTRACT_STATUS = {
        "draft": "草稿",
        "pending_review": "审核中",
        "active": "生效中",
        "expired": "已过期",
        "terminated": "已终止",
        "renewed": "已续约",
    }

    # 事件类型映射
    EVENT_TYPES = {
        "created": "创建合同",
        "submitted": "提交审核",
        "approved": "审核通过",
        "signed": "已签署",
        "amended": "修订",
        "renewed": "续约",
        "expired": "已过期",
        "terminated": "终止",
    }

    async def create_contract(self, org_id: str, data: dict, db: Any = None) -> dict:
        """创建新合同"""
        contract = {
            "organization_id": org_id,
            "title": data.get("title", ""),
            "customer_id": data.get("customer_id"),
            "contract_number": data.get("contract_number", ""),
            "contract_type": data.get("contract_type", "sales"),
            "status": data.get("status", "draft"),
            "amount": data.get("amount"),
            "currency": data.get("currency", "CNY"),
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            "document_url": data.get("document_url"),
            "tags": data.get("tags", []),
            "metadata": data.get("metadata", {}),
        }

        if db:
            try:
                result = await db.table("contracts").insert(contract).execute()
                if result.data:
                    created = result.data[0]
                    # 添加创建事件
                    await self.add_contract_event(
                        contract_id=created["id"],
                        event_type="created",
                        description=f"合同「{contract['title']}」已创建",
                        user_id=data.get("created_by"),
                        db=db,
                    )
                    return created
            except Exception as e:
                logger.error(f"Failed to create contract: {e}")
                raise

        return {**contract, "id": "mock-id", "created_at": datetime.utcnow().isoformat()}

    async def update_contract(self, contract_id: str, data: dict, db: Any = None) -> dict:
        """更新合同"""
        update_data = {
            k: v
            for k, v in data.items()
            if k
            in (
                "title",
                "contract_number",
                "contract_type",
                "status",
                "amount",
                "currency",
                "start_date",
                "end_date",
                "document_url",
                "tags",
                "metadata",
                "signed_by",
                "signed_at",
                "customer_id",
            )
            and v is not None
        }
        update_data["updated_at"] = datetime.utcnow().isoformat()

        if db:
            try:
                result = await db.table("contracts").update(update_data).eq("id", contract_id).execute()
                if result.data:
                    return result.data[0]
            except Exception as e:
                logger.error(f"Failed to update contract: {e}")
                raise

        return {"id": contract_id, **update_data}

    async def get_contract(self, contract_id: str, db: Any = None) -> dict | None:
        """获取合同详情"""
        if db:
            try:
                result = await db.table("contracts").select("*").eq("id", contract_id).single().execute()
                return result.data
            except Exception as e:
                logger.warning(f"Failed to get contract: {e}")
                return None
        return None

    async def list_contracts(
        self,
        org_id: str,
        filters: dict | None = None,
        db: Any = None,
    ) -> list[dict]:
        """列出组织的合同"""
        if db:
            try:
                query = db.table("contracts").select("*").eq("organization_id", org_id).order("created_at", desc=True)

                if filters:
                    if filters.get("status"):
                        query = query.eq("status", filters["status"])
                    if filters.get("contract_type"):
                        query = query.eq("contract_type", filters["contract_type"])
                    if filters.get("search"):
                        query = query.ilike("title", f"%{filters['search']}%")

                result = await query.execute()
                return result.data or []
            except Exception as e:
                logger.error(f"Failed to list contracts: {e}")
                return []
        return []

    async def get_expiring_contracts(self, org_id: str, days: int = 30, db: Any = None) -> list[dict]:
        """获取即将到期的合同"""
        if db:
            try:
                today = datetime.utcnow().date().isoformat()
                future = (datetime.utcnow() + timedelta(days=days)).date().isoformat()
                result = (
                    await db.table("contracts")
                    .select("*")
                    .eq("organization_id", org_id)
                    .eq("status", "active")
                    .gte("end_date", today)
                    .lte("end_date", future)
                    .order("end_date", desc=False)
                    .execute()
                )
                return result.data or []
            except Exception as e:
                logger.error(f"Failed to get expiring contracts: {e}")
                return []
        return []

    async def get_contract_stats(self, org_id: str, db: Any = None) -> dict:
        """合同统计"""
        stats: dict[str, Any] = {
            "total": 0,
            "total_amount": 0,
            "by_status": {},
            "by_type": {},
            "expiring_soon": 0,
        }

        if db:
            try:
                # 获取所有合同
                result = await db.table("contracts").select("*").eq("organization_id", org_id).execute()
                contracts = result.data or []
                stats["total"] = len(contracts)

                for c in contracts:
                    # 按状态统计
                    status = c.get("status", "draft")
                    stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

                    # 按类型统计
                    ctype = c.get("contract_type", "other")
                    stats["by_type"][ctype] = stats["by_type"].get(ctype, 0) + 1

                    # 总金额
                    amount = c.get("amount")
                    if amount:
                        stats["total_amount"] += float(amount)

                # 即将到期数
                expiring = await self.get_expiring_contracts(org_id, days=30, db=db)
                stats["expiring_soon"] = len(expiring)

            except Exception as e:
                logger.error(f"Failed to get contract stats: {e}")

        return stats

    async def add_contract_event(
        self,
        contract_id: str,
        event_type: str,
        description: str,
        user_id: str | None = None,
        db: Any = None,
    ) -> dict:
        """添加合同事件"""
        event = {
            "contract_id": contract_id,
            "event_type": event_type,
            "description": description,
            "user_id": user_id,
        }

        if db:
            try:
                result = await db.table("contract_events").insert(event).execute()
                if result.data:
                    return result.data[0]
            except Exception as e:
                logger.error(f"Failed to add contract event: {e}")
                raise

        return {**event, "id": "mock-event-id", "created_at": datetime.utcnow().isoformat()}

    async def get_contract_events(self, contract_id: str, db: Any = None) -> list[dict]:
        """获取合同事件时间线"""
        if db:
            try:
                result = (
                    await db.table("contract_events")
                    .select("*")
                    .eq("contract_id", contract_id)
                    .order("created_at", desc=True)
                    .execute()
                )
                return result.data or []
            except Exception as e:
                logger.error(f"Failed to get contract events: {e}")
                return []
        return []


contract_service = ContractService()
