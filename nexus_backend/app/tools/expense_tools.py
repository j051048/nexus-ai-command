"""
报销管理工具集
提供报销申请、审批、预算查询等功能
"""

import logging
import uuid as _uuid
from typing import Any

from app.core.database import supabase
from app.services.expense_service import expense_service

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


def _get_client(config: dict = None):
    """Get scoped DB client if user token available, else fallback to service client."""
    token = config.get("token") if config else None
    return supabase.get_scoped_client(token) if token and supabase else supabase


def _get_org_id(config: dict = None) -> str | None:
    return config.get("org_id") if config else None


def _validate_uuid(value: str, field_name: str = "ID") -> str | None:
    """验证UUID格式"""
    try:
        _uuid.UUID(value)
        return None
    except (ValueError, TypeError, AttributeError):
        return f"{field_name} '{value}' 不是有效的UUID格式。"


# ============================================================================
# 报销管理工具
# ============================================================================


class SubmitExpenseTool(BaseTool):
    """提交报销申请"""

    name = "submit_expense"
    description = "提交报销申请。当用户说'报销'、'提交报销'、'报销申请'时调用。"

    is_irreversible = True

    parameters = {
        "type": "object",
        "properties": {
            "expense_type": {
                "type": "string",
                "description": "报销类型（如: travel, meal, office, transport等）",
            },
            "total_amount": {
                "type": "number",
                "description": "报销总金额",
                "minimum": 0.01,
                "maximum": 99999999,
            },
            "items": {
                "type": "array",
                "description": "报销明细列表（可选）",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string", "description": "费用说明"},
                        "amount": {"type": "number", "description": "金额"},
                        "date": {"type": "string", "description": "消费日期 YYYY-MM-DD"},
                    },
                },
            },
        },
        "required": ["expense_type", "total_amount"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        expense_type = args.get("expense_type", "").strip()
        total_amount = args.get("total_amount")
        items = args.get("items")

        if not expense_type:
            return "❌ 报销类型不能为空"
        if not total_amount or total_amount <= 0:
            return "❌ 报销金额必须大于0"

        try:
            claim = await expense_service.submit_expense(
                org_id=org_id,
                employee_id=user_id,
                expense_type=expense_type,
                total_amount=total_amount,
                items=items,
                db=client,
            )

            type_labels = {
                "travel": "差旅费",
                "meal": "餐饮费",
                "office": "办公用品",
                "transport": "交通费",
            }
            etype = type_labels.get(expense_type, expense_type)

            return (
                f"✅ 报销单提交成功！\n\n"
                f"- 报销单号: {claim.get('claim_no', '')}\n"
                f"- 报销类型: {etype}\n"
                f"- 金额: ¥{total_amount:,.2f}\n"
                f"- 状态: 待审批\n"
                f"- ID: {claim['id']}\n\n"
                f"报销单已提交，等待审批。"
            )

        except Exception as e:
            logger.error(f"提交报销失败: {e}")
            return f"❌ 提交报销失败: {str(e)}"


class ListExpensesTool(BaseTool):
    """查询报销记录"""

    name = "list_expenses"
    description = "查询报销记录。当用户说'查看报销'、'报销列表'、'报销记录'时调用。"

    parameters = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "报销状态",
                "enum": ["pending", "approved", "rejected"],
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

        filters = {}
        if args.get("status"):
            filters["status"] = args["status"]
        if args.get("start_date"):
            filters["start_date"] = args["start_date"]
        if args.get("end_date"):
            filters["end_date"] = args["end_date"]

        try:
            claims = await expense_service.list_expenses(
                org_id=org_id,
                filters=filters or None,
                db=client,
            )

            if not claims:
                return "📋 当前暂无报销记录。"

            status_labels = {
                "pending": "待审批",
                "approved": "已通过",
                "rejected": "已驳回",
            }
            type_labels = {
                "travel": "差旅费",
                "meal": "餐饮费",
                "office": "办公用品",
                "transport": "交通费",
            }

            lines = [f"💰 共找到 {len(claims)} 条报销记录:\n"]
            for c in claims:
                status = status_labels.get(c.get("status", ""), c.get("status", ""))
                etype = type_labels.get(c.get("expense_type", ""), c.get("expense_type", ""))
                lines.append(
                    f"- **{etype}** | 单号: {c.get('claim_no', '')} | "
                    f"金额: ¥{c.get('total_amount', 0):,.2f} | "
                    f"状态: {status} | 日期: {str(c.get('created_at', ''))[:10]}"
                )

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"查询报销记录失败: {e}")
            return f"❌ 查询报销记录失败: {str(e)}"


class ApproveExpenseTool(BaseTool):
    """审批报销单"""

    name = "approve_expense"
    description = "审批报销单（通过或驳回）。当用户说'审批报销'、'批准报销'、'驳回报销'时调用。"

    required_role = "admin"

    parameters = {
        "type": "object",
        "properties": {
            "expense_id": {
                "type": "string",
                "description": "报销单ID",
            },
            "action": {
                "type": "string",
                "description": "审批动作",
                "enum": ["approve", "reject"],
            },
            "comment": {
                "type": "string",
                "description": "审批意见（可选）",
                "maxLength": 500,
            },
        },
        "required": ["expense_id", "action"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        expense_id = args.get("expense_id", "").strip()
        action = args.get("action", "").strip()
        comment = args.get("comment")

        if not expense_id or not action:
            return "❌ 报销单ID和审批动作不能为空"

        if err := _validate_uuid(expense_id, "expense_id"):
            return f"❌ {err}"

        if action not in ("approve", "reject"):
            return "❌ 审批动作必须是 approve 或 reject"

        try:
            claim = await expense_service.approve_expense(
                expense_id=expense_id,
                action=action,
                comment=comment,
                db=client,
            )

            action_label = "通过" if action == "approve" else "驳回"

            return (
                f"✅ 报销单已{action_label}！\n\n"
                f"- 报销单号: {claim.get('claim_no', '')}\n"
                f"- 金额: ¥{claim.get('total_amount', 0)}\n"
                f"- 状态: {claim.get('status', '')}"
            )

        except Exception as e:
            logger.error(f"审批报销失败: {e}")
            return f"❌ 审批报销失败: {str(e)}"


class CheckBudgetTool(BaseTool):
    """查询预算使用情况"""

    name = "check_budget"
    description = "查询预算使用情况。当用户说'预算查询'、'预算余额'、'查看预算'时调用。"

    parameters = {
        "type": "object",
        "properties": {
            "department_id": {
                "type": "string",
                "description": "部门ID（可选）",
            },
            "period": {
                "type": "string",
                "description": "预算周期（可选，如 2026-03）",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        department_id = args.get("department_id")
        period = args.get("period")

        if department_id:
            department_id = department_id.strip()

        try:
            budget = await expense_service.check_budget(
                org_id=org_id,
                department_id=department_id,
                period=period,
                db=client,
            )

            return (
                f"💼 预算使用情况:\n\n"
                f"- 总预算: ¥{budget.get('total', 0):,.2f}\n"
                f"- 已使用: ¥{budget.get('used', 0):,.2f}\n"
                f"- 剩余: ¥{budget.get('remaining', 0):,.2f}\n"
                f"- 使用率: {budget.get('utilization_rate', 0)}%"
            )

        except Exception as e:
            logger.error(f"查询预算失败: {e}")
            return f"❌ 查询预算失败: {str(e)}"
