"""
工单系统服务
提供通用工单管理功能
"""

import logging
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)


class WorkOrderService:
    """工单管理服务"""

    async def list_work_orders(
        self,
        org_id: str,
        filters: dict | None = None,
        db=None,
    ) -> list[dict]:
        """
        查询工单列表

        Args:
            org_id: 组织ID
            filters: 筛选条件 {order_type, status, priority, assignee_id, creator_id, search}
            db: 数据库客户端

        Returns:
            工单列表
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            query = (
                db.table("work_orders")
                .select("*")
                .eq("organization_id", org_id)
                .order("created_at", desc=True)
            )

            if filters:
                if filters.get("order_type"):
                    query = query.eq("order_type", filters["order_type"])
                if filters.get("status"):
                    query = query.eq("status", filters["status"])
                if filters.get("priority"):
                    query = query.eq("priority", filters["priority"])
                if filters.get("assignee_id"):
                    query = query.eq("assignee_id", filters["assignee_id"])
                if filters.get("creator_id"):
                    query = query.eq("creator_id", filters["creator_id"])
                if filters.get("search"):
                    search = filters["search"]
                    query = query.or_(f"title.ilike.%{search}%,description.ilike.%{search}%")

            result = await query.execute()
            return result.data or []

        except Exception as e:
            logger.error(f"查询工单列表失败: {e}")
            raise

    async def get_work_order_detail(
        self,
        order_id: str,
        db=None,
    ) -> dict | None:
        """
        获取工单详情

        Args:
            order_id: 工单ID
            db: 数据库客户端

        Returns:
            工单详情
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            result = await (
                db.table("work_orders")
                .select("*")
                .eq("id", order_id)
                .maybe_single()
                .execute()
            )

            return result.data

        except Exception as e:
            logger.error(f"获取工单详情失败: {e}")
            raise

    async def create_work_order(
        self,
        org_id: str,
        creator_id: str,
        data: dict,
        db=None,
    ) -> dict:
        """
        创建工单

        Args:
            org_id: 组织ID
            creator_id: 创建人ID
            data: 工单数据
            db: 数据库客户端

        Returns:
            工单对象
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            data["organization_id"] = org_id
            data["creator_id"] = creator_id
            data.setdefault("status", "open")
            data.setdefault("priority", "medium")

            # 根据工单类型设置 SLA
            order_type = data.get("order_type")
            if order_type:
                type_result = await (
                    db.table("work_order_types")
                    .select("sla_hours")
                    .eq("organization_id", org_id)
                    .eq("name", order_type)
                    .maybe_single()
                    .execute()
                )

                if type_result.data and type_result.data.get("sla_hours"):
                    sla_hours = type_result.data["sla_hours"]
                    data["due_date"] = (datetime.now(UTC) + timedelta(hours=sla_hours)).isoformat()

            result = await db.table("work_orders").insert(data).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"工单已创建: org={org_id}, title={data.get('title')}")
                return result.data[0]

            raise RuntimeError("工单创建失败")

        except Exception as e:
            logger.error(f"创建工单失败: {e}")
            raise

    async def update_work_order(
        self,
        order_id: str,
        user_id: str,
        updates: dict,
        comment: str | None = None,
        db=None,
    ) -> dict:
        """
        更新工单

        Args:
            order_id: 工单ID
            user_id: 操作人ID
            updates: 更新字段
            comment: 备注
            db: 数据库客户端

        Returns:
            更新后的工单对象
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            # 更新工单
            result = await db.table("work_orders").update(updates).eq("id", order_id).execute()

            if not result.data or len(result.data) == 0:
                raise RuntimeError("工单更新失败")

            # 记录评论
            if comment or updates.get("status") or updates.get("assignee_id"):
                comment_data = {
                    "order_id": order_id,
                    "user_id": user_id,
                    "content": comment or "",
                    "comment_type": "status_change" if updates.get("status") else "comment",
                    "metadata": {},
                }

                if updates.get("status"):
                    comment_data["metadata"]["status_change"] = {"to": updates["status"]}

                if updates.get("assignee_id"):
                    comment_data["metadata"]["assignee_change"] = {"to": updates["assignee_id"]}

                await db.table("work_order_comments").insert(comment_data).execute()

            logger.info(f"工单已更新: id={order_id}")
            return result.data[0]

        except Exception as e:
            logger.error(f"更新工单失败: {e}")
            raise

    async def get_work_order_comments(
        self,
        order_id: str,
        db=None,
    ) -> list[dict]:
        """
        获取工单评论列表

        Args:
            order_id: 工单ID
            db: 数据库客户端

        Returns:
            评论列表
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            result = await (
                db.table("work_order_comments")
                .select("*")
                .eq("order_id", order_id)
                .order("created_at", desc=False)
                .execute()
            )

            return result.data or []

        except Exception as e:
            logger.error(f"获取工单评论失败: {e}")
            raise

    async def get_work_order_statistics(
        self,
        org_id: str,
        order_type: str | None = None,
        time_range: dict | None = None,
        db=None,
    ) -> dict:
        """
        获取工单统计数据

        Args:
            org_id: 组织ID
            order_type: 工单类型（可选）
            time_range: 时间范围 {start_date, end_date}
            db: 数据库客户端

        Returns:
            统计数据
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            query = db.table("work_orders").select("*").eq("organization_id", org_id)

            if order_type:
                query = query.eq("order_type", order_type)

            if time_range:
                if time_range.get("start_date"):
                    query = query.gte("created_at", time_range["start_date"])
                if time_range.get("end_date"):
                    query = query.lte("created_at", time_range["end_date"])

            result = await query.execute()
            orders = result.data or []

            total_count = len(orders)
            open_count = sum(1 for o in orders if o.get("status") == "open")
            processing_count = sum(1 for o in orders if o.get("status") == "processing")
            resolved_count = sum(1 for o in orders if o.get("status") == "resolved")
            closed_count = sum(1 for o in orders if o.get("status") == "closed")

            # 计算平均响应时长（创建到处理中）
            response_times = []
            for order in orders:
                if order.get("status") in ["processing", "resolved", "closed"]:
                    created_at = datetime.fromisoformat(order["created_at"].replace("Z", "+00:00"))
                    updated_at = datetime.fromisoformat(order["updated_at"].replace("Z", "+00:00"))
                    response_times.append((updated_at - created_at).total_seconds() / 3600)

            avg_response_hours = round(sum(response_times) / len(response_times), 2) if response_times else 0

            # SLA 达标率
            sla_met_count = 0
            for order in orders:
                if order.get("due_date") and order.get("resolved_at"):
                    due_date = datetime.fromisoformat(order["due_date"].replace("Z", "+00:00"))
                    resolved_at = datetime.fromisoformat(order["resolved_at"].replace("Z", "+00:00"))
                    if resolved_at <= due_date:
                        sla_met_count += 1

            resolved_total = resolved_count + closed_count
            sla_rate = round(sla_met_count / resolved_total * 100, 2) if resolved_total > 0 else 0

            return {
                "total_count": total_count,
                "open_count": open_count,
                "processing_count": processing_count,
                "resolved_count": resolved_count,
                "closed_count": closed_count,
                "avg_response_hours": avg_response_hours,
                "sla_met_rate": sla_rate,
            }

        except Exception as e:
            logger.error(f"获取工单统计失败: {e}")
            raise

    async def list_work_order_types(
        self,
        org_id: str,
        db=None,
    ) -> list[dict]:
        """
        查询工单类型列表

        Args:
            org_id: 组织ID
            db: 数据库客户端

        Returns:
            工单类型列表
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            result = await db.table("work_order_types").select("*").eq("organization_id", org_id).execute()

            return result.data or []

        except Exception as e:
            logger.error(f"查询工单类型列表失败: {e}")
            raise

    async def create_work_order_type(
        self,
        org_id: str,
        name: str,
        sla_hours: int = 24,
        icon: str | None = None,
        color: str | None = None,
        db=None,
    ) -> dict:
        """
        创建工单类型

        Args:
            org_id: 组织ID
            name: 类型名称
            sla_hours: SLA时长（小时）
            icon: 图标
            color: 颜色
            db: 数据库客户端

        Returns:
            工单类型对象
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            data = {
                "organization_id": org_id,
                "name": name,
                "sla_hours": sla_hours,
                "icon": icon,
                "color": color,
            }

            result = await db.table("work_order_types").insert(data).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"工单类型已创建: org={org_id}, name={name}")
                return result.data[0]

            raise RuntimeError("工单类型创建失败")

        except Exception as e:
            logger.error(f"创建工单类型失败: {e}")
            raise


work_order_service = WorkOrderService()
