"""
工单系统工具集
提供通用工单管理功能（报修、投诉、申请等）
"""

import logging
from typing import Any

from app.services.work_order_service import work_order_service

from .base_tool import BaseTool
from ._shared import _get_client, _validate_uuid

logger = logging.getLogger(__name__)


def _get_org_id(config: dict = None) -> str | None:
    return config.get("org_id") if config else None


# ============================================================================
# 工单管理工具
# ============================================================================


class CreateWorkOrderTool(BaseTool):
    """创建工单"""

    name = "create_work_order"
    description = "创建新工单（报修、投诉、申请等）。当用户说'创建工单'、'提交报修'、'提交投诉'、'提交申请'时调用。"

    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "工单标题",
                "maxLength": 200,
            },
            "order_type": {
                "type": "string",
                "description": "工单类型（如: repair, complaint, request, consultation）",
                "maxLength": 50,
            },
            "description": {
                "type": "string",
                "description": "工单描述",
                "maxLength": 2000,
            },
            "priority": {
                "type": "string",
                "description": "优先级",
                "enum": ["low", "medium", "high", "urgent"],
            },
            "assignee_id": {
                "type": "string",
                "description": "指派处理人ID（可选）",
            },
            "department_id": {
                "type": "string",
                "description": "所属部门ID（可选）",
            },
        },
        "required": ["title", "order_type"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        title = args.get("title", "").strip()
        order_type = args.get("order_type", "").strip()

        if not title or not order_type:
            return "❌ 工单标题和类型不能为空"

        if args.get("assignee_id") and (err := _validate_uuid(args["assignee_id"], "assignee_id")):
            return f"❌ {err}"

        if args.get("department_id") and (err := _validate_uuid(args["department_id"], "department_id")):
            return f"❌ {err}"

        data = {
            "title": title,
            "order_type": order_type,
        }

        for field in ["description", "priority", "assignee_id", "department_id"]:
            if args.get(field):
                data[field] = args[field]

        try:
            order = await work_order_service.create_work_order(
                org_id=org_id,
                creator_id=user_id,
                data=data,
                db=client,
            )

            type_labels = {
                "repair": "设备报修",
                "complaint": "客户投诉",
                "request": "物资申请",
                "consultation": "咨询",
            }
            otype = type_labels.get(order_type, order_type)
            priority_labels = {"low": "低", "medium": "中", "high": "高", "urgent": "紧急"}
            prio = priority_labels.get(order.get("priority", ""), order.get("priority", ""))

            return (
                f"✅ 工单创建成功！\n\n"
                f"- 标题: {order.get('title')}\n"
                f"- 类型: {otype}\n"
                f"- 优先级: {prio}\n"
                f"- 状态: 待处理\n"
                f"- ID: {order['id']}\n\n"
                f"工单已创建，等待处理。"
            )

        except Exception as e:
            logger.error(f"创建工单失败: {e}")
            return f"❌ 创建工单失败: {str(e)}"


class ListWorkOrdersTool(BaseTool):
    """查询工单列表"""

    name = "list_work_orders"
    description = (
        "查询工单列表，支持按类型、状态、优先级筛选。当用户说'查看工单'、'工单列表'、'有哪些待处理工单'时调用。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "order_type": {
                "type": "string",
                "description": "工单类型（可选）",
            },
            "status": {
                "type": "string",
                "description": "工单状态",
                "enum": ["open", "processing", "resolved", "closed", "cancelled"],
            },
            "priority": {
                "type": "string",
                "description": "优先级",
                "enum": ["low", "medium", "high", "urgent"],
            },
            "assignee_id": {
                "type": "string",
                "description": "处理人ID（可选）",
            },
            "search": {
                "type": "string",
                "description": "搜索关键词",
                "maxLength": 100,
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        filters = {}
        if args.get("order_type"):
            filters["order_type"] = args["order_type"]
        if args.get("status"):
            filters["status"] = args["status"]
        if args.get("priority"):
            filters["priority"] = args["priority"]
        if args.get("assignee_id"):
            if err := _validate_uuid(args["assignee_id"], "assignee_id"):
                return f"❌ {err}"
            filters["assignee_id"] = args["assignee_id"]
        if args.get("search"):
            filters["search"] = args["search"]

        try:
            orders = await work_order_service.list_work_orders(
                org_id=org_id,
                filters=filters or None,
                db=client,
            )

            if not orders:
                return "当前暂无工单记录。"

            status_labels = {
                "open": "待处理",
                "processing": "处理中",
                "resolved": "已解决",
                "closed": "已关闭",
                "cancelled": "已取消",
            }
            priority_labels = {"low": "低", "medium": "中", "high": "高", "urgent": "🔴紧急"}

            lines = [f"📋 共找到 {len(orders)} 个工单:\n"]
            for order in orders:
                status = status_labels.get(order.get("status", ""), order.get("status", ""))
                prio = priority_labels.get(order.get("priority", ""), order.get("priority", ""))
                assignee = order.get("assignee", {})
                assignee_name = assignee.get("name", "未分配") if assignee else "未分配"

                lines.append(
                    f"- **{order.get('title')}** | 类型: {order.get('order_type')} | "
                    f"优先级: {prio} | 状态: {status} | "
                    f"处理人: {assignee_name} | ID: {order['id'][:8]}..."
                )

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"查询工单列表失败: {e}")
            return f"❌ 查询工单列表失败: {str(e)}"


class GetWorkOrderDetailTool(BaseTool):
    """获取工单详情"""

    name = "get_work_order_detail"
    description = "获取工单详细信息。当用户说'查看工单详情'、'工单信息'时调用。"

    parameters = {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "工单ID",
            },
        },
        "required": ["order_id"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        order_id = args.get("order_id")

        if err := _validate_uuid(order_id, "order_id"):
            return f"❌ {err}"

        try:
            order = await work_order_service.get_work_order_detail(
                order_id=order_id,
                db=client,
            )

            if not order:
                return f"❌ 未找到ID为 {order_id} 的工单。"

            status_labels = {
                "open": "待处理",
                "processing": "处理中",
                "resolved": "已解决",
                "closed": "已关闭",
                "cancelled": "已取消",
            }
            priority_labels = {"low": "低", "medium": "中", "high": "高", "urgent": "紧急"}
            status = status_labels.get(order.get("status", ""), order.get("status", ""))
            prio = priority_labels.get(order.get("priority", ""), order.get("priority", ""))
            assignee = order.get("assignee", {})
            assignee_name = assignee.get("name", "未分配") if assignee else "未分配"

            result = (
                f"📝 工单详情:\n\n"
                f"- 标题: {order.get('title')}\n"
                f"- 类型: {order.get('order_type')}\n"
                f"- 优先级: {prio}\n"
                f"- 状态: {status}\n"
                f"- 处理人: {assignee_name}\n"
                f"- 描述: {order.get('description', '无')}\n"
                f"- 创建时间: {str(order.get('created_at', ''))[:19]}\n"
                f"- 截止时间: {str(order.get('due_date', '未设定'))[:19]}\n"
                f"- ID: {order['id']}"
            )

            # 获取评论
            comments = await work_order_service.get_work_order_comments(
                order_id=order_id,
                db=client,
            )

            if comments:
                result += f"\n\n💬 流转记录 ({len(comments)}条):"
                for c in comments[-5:]:  # 最近5条
                    result += f"\n  [{str(c.get('created_at', ''))[:16]}] {c.get('content', '')}"

            return result

        except Exception as e:
            logger.error(f"获取工单详情失败: {e}")
            return f"❌ 获取工单详情失败: {str(e)}"


class UpdateWorkOrderTool(BaseTool):
    """更新工单"""

    name = "update_work_order"
    description = "更新工单状态、指派处理人或添加备注。当用户说'处理工单'、'更新工单'、'关闭工单'、'指派工单'时调用。"

    parameters = {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "工单ID",
            },
            "status": {
                "type": "string",
                "description": "工单状态",
                "enum": ["open", "processing", "resolved", "closed", "cancelled"],
            },
            "assignee_id": {
                "type": "string",
                "description": "处理人ID（可选）",
            },
            "comment": {
                "type": "string",
                "description": "备注/处理说明",
                "maxLength": 1000,
            },
        },
        "required": ["order_id"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        order_id = args.get("order_id")

        if err := _validate_uuid(order_id, "order_id"):
            return f"❌ {err}"

        updates = {}
        if args.get("status"):
            updates["status"] = args["status"]
            if args["status"] == "resolved":
                from datetime import UTC, datetime

                updates["resolved_at"] = datetime.now(UTC).isoformat()
        if args.get("assignee_id"):
            if err := _validate_uuid(args["assignee_id"], "assignee_id"):
                return f"❌ {err}"
            updates["assignee_id"] = args["assignee_id"]

        comment = args.get("comment")

        if not updates and not comment:
            return "❌ 请提供至少一个要更新的字段或备注"

        try:
            order = await work_order_service.update_work_order(
                order_id=order_id,
                user_id=user_id,
                updates=updates,
                comment=comment,
                db=client,
            )

            status_labels = {
                "open": "待处理",
                "processing": "处理中",
                "resolved": "已解决",
                "closed": "已关闭",
                "cancelled": "已取消",
            }
            status = status_labels.get(order.get("status", ""), order.get("status", ""))

            return f"✅ 工单已更新: {order.get('title')} → 状态: {status}"

        except Exception as e:
            logger.error(f"更新工单失败: {e}")
            return f"❌ 更新工单失败: {str(e)}"


class WorkOrderStatisticsTool(BaseTool):
    """工单统计"""

    name = "work_order_statistics"
    description = (
        "获取工单统计数据（总量、处理率、响应时长、SLA达标率等）。当用户说'工单统计'、'工单分析'、'处理效率'时调用。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "order_type": {
                "type": "string",
                "description": "工单类型（可选，不填则统计全部）",
            },
            "start_date": {
                "type": "string",
                "description": "开始日期 YYYY-MM-DD（可选）",
            },
            "end_date": {
                "type": "string",
                "description": "结束日期 YYYY-MM-DD（可选）",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        time_range = {}
        if args.get("start_date"):
            time_range["start_date"] = args["start_date"]
        if args.get("end_date"):
            time_range["end_date"] = args["end_date"]

        try:
            stats = await work_order_service.get_work_order_statistics(
                org_id=org_id,
                order_type=args.get("order_type"),
                time_range=time_range or None,
                db=client,
            )

            type_label = args.get("order_type", "全部")

            return (
                f"📊 工单统计 ({type_label}):\n\n"
                f"- 工单总数: {stats.get('total_count')}\n"
                f"- 待处理: {stats.get('open_count')}\n"
                f"- 处理中: {stats.get('processing_count')}\n"
                f"- 已解决: {stats.get('resolved_count')}\n"
                f"- 已关闭: {stats.get('closed_count')}\n"
                f"- 平均响应时长: {stats.get('avg_response_hours')}小时\n"
                f"- SLA达标率: {stats.get('sla_met_rate')}%"
            )

        except Exception as e:
            logger.error(f"获取工单统计失败: {e}")
            return f"❌ 获取工单统计失败: {str(e)}"
