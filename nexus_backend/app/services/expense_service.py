"""
报销管理服务
提供报销申请、审批、预算等功能
"""

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


class ExpenseService:
    """报销管理服务"""

    async def submit_expense(
        self,
        org_id: str,
        employee_id: str,
        expense_type: str,
        total_amount: float,
        items: list[dict] | None = None,
        db=None,
    ) -> dict:
        """
        提交报销申请

        Args:
            org_id: 组织ID
            employee_id: 员工ID
            expense_type: 报销类型
            total_amount: 总金额
            items: 报销明细列表
            db: 数据库客户端

        Returns:
            报销单
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            # 生成报销单号
            timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
            claim_no = f"EXP-{timestamp}"

            claim_data = {
                "organization_id": org_id,
                "employee_id": employee_id,
                "claim_no": claim_no,
                "expense_type": expense_type,
                "total_amount": total_amount,
                "status": "pending",
            }

            result = await db.table("expense_claims").insert(claim_data).execute()

            if not result.data or len(result.data) == 0:
                raise RuntimeError("报销单创建失败")

            claim = result.data[0]

            # 插入报销明细
            if items:
                for item in items:
                    item["claim_id"] = claim["id"]
                    item["organization_id"] = org_id

                await db.table("expense_items").insert(items).execute()

            logger.info(f"报销单已提交: org={org_id}, claim_no={claim_no}, amount={total_amount}")
            return claim

        except Exception as e:
            logger.error(f"提交报销申请失败: {e}")
            raise

    async def list_expenses(
        self,
        org_id: str,
        filters: dict | None = None,
        db=None,
    ) -> list[dict]:
        """
        查询报销单列表

        Args:
            org_id: 组织ID
            filters: 筛选条件 {employee_id, status, start_date, end_date}
            db: 数据库客户端

        Returns:
            报销单列表
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            query = db.table("expense_claims").select("*").eq("organization_id", org_id).order("created_at", desc=True)

            if filters:
                if filters.get("employee_id"):
                    query = query.eq("employee_id", filters["employee_id"])
                if filters.get("status"):
                    query = query.eq("status", filters["status"])
                if filters.get("start_date"):
                    query = query.gte("created_at", filters["start_date"])
                if filters.get("end_date"):
                    query = query.lte("created_at", filters["end_date"])

            result = await query.execute()
            return result.data or []

        except Exception as e:
            logger.error(f"查询报销单列表失败: {e}")
            raise

    async def approve_expense(
        self,
        expense_id: str,
        action: str,
        comment: str | None = None,
        db=None,
    ) -> dict:
        """
        审批报销单

        Args:
            expense_id: 报销单ID
            action: 审批动作 (approve/reject)
            comment: 审批备注
            db: 数据库客户端

        Returns:
            更新后的报销单
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            status = "approved" if action == "approve" else "rejected"
            updates = {
                "status": status,
                "reviewed_at": datetime.now(UTC).isoformat(),
            }
            if comment:
                updates["review_comment"] = comment

            result = await db.table("expense_claims").update(updates).eq("id", expense_id).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"报销单已审批: id={expense_id}, action={action}")
                return result.data[0]

            raise RuntimeError("报销单审批失败")

        except Exception as e:
            logger.error(f"审批报销单失败: {e}")
            raise

    async def get_expense_statistics(
        self,
        org_id: str,
        filters: dict | None = None,
        db=None,
    ) -> dict:
        """
        获取报销统计数据

        Args:
            org_id: 组织ID
            filters: 筛选条件 {start_date, end_date}
            db: 数据库客户端

        Returns:
            统计数据
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            query = db.table("expense_claims").select("*").eq("organization_id", org_id)

            if filters:
                if filters.get("start_date"):
                    query = query.gte("created_at", filters["start_date"])
                if filters.get("end_date"):
                    query = query.lte("created_at", filters["end_date"])

            result = await query.execute()
            claims = result.data or []

            total_count = len(claims)
            total_amount = sum(float(c.get("total_amount") or 0) for c in claims)

            # 按类型分组统计
            by_type: dict[str, dict] = {}
            for claim in claims:
                expense_type = claim.get("expense_type", "other")
                if expense_type not in by_type:
                    by_type[expense_type] = {"count": 0, "amount": 0}
                by_type[expense_type]["count"] += 1
                by_type[expense_type]["amount"] += float(claim.get("total_amount") or 0)

            # 四舍五入金额
            for type_data in by_type.values():
                type_data["amount"] = round(type_data["amount"], 2)

            return {
                "total_count": total_count,
                "total_amount": round(total_amount, 2),
                "pending_count": sum(1 for c in claims if c.get("status") == "pending"),
                "approved_count": sum(1 for c in claims if c.get("status") == "approved"),
                "rejected_count": sum(1 for c in claims if c.get("status") == "rejected"),
                "by_type": by_type,
            }

        except Exception as e:
            logger.error(f"获取报销统计失败: {e}")
            raise

    async def check_budget(
        self,
        org_id: str,
        department_id: str | None = None,
        period: str | None = None,
        db=None,
    ) -> dict:
        """
        查询预算使用情况

        Args:
            org_id: 组织ID
            department_id: 部门ID（TEXT类型，可选）
            period: 预算周期（可选，如 2026-03）
            db: 数据库客户端

        Returns:
            预算信息 {total, used, remaining}
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            query = db.table("budgets").select("*").eq("organization_id", org_id)

            if department_id:
                query = query.eq("department_id", department_id)
            if period:
                query = query.eq("period", period)

            result = await query.execute()
            budgets = result.data or []

            total_budget = sum(float(b.get("total_amount") or 0) for b in budgets)
            used_budget = sum(float(b.get("used_amount") or 0) for b in budgets)
            remaining = total_budget - used_budget

            return {
                "total": round(total_budget, 2),
                "used": round(used_budget, 2),
                "remaining": round(remaining, 2),
                "utilization_rate": round(used_budget / total_budget * 100, 2) if total_budget > 0 else 0,
            }

        except Exception as e:
            logger.error(f"查询预算失败: {e}")
            raise


expense_service = ExpenseService()
