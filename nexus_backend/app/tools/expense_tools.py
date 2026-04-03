"""
报销管理工具集
提供报销申请、审批、预算查询等功能
"""

import logging
from typing import Any

from app.services.expense_service import expense_service
from app.tools._shared import safe_tool_error

from ._shared import _get_client, _validate_uuid
from .base_tool import BaseTool

logger = logging.getLogger(__name__)


def _get_org_id(config: dict = None) -> str | None:
    return config.get("org_id") if config else None


# ============================================================================
# 报销管理工具
# ============================================================================


class SubmitExpenseTool(BaseTool):
    """提交报销申请"""

    name = "submit_expense"
    description = "提交报销申请，支持差旅、餐饮、办公用品、交通等类型"
    examples = [
        {"input": {"expense_type": "travel", "total_amount": 3500}, "output_summary": "提交一笔3500元的差旅费报销"},
        {"input": {"expense_type": "meal", "total_amount": 280, "items": [{"description": "客户午餐", "amount": 280, "date": "2026-03-15"}]}, "output_summary": "提交一笔带明细的餐饮费报销"},
    ]
    gotchas = "total_amount必须大于0。expense_type常用值：travel/meal/office/transport。提交后状态为pending（待审批）。建议先调用check_budget确认预算余额。"
    related_tools = ["list_expenses", "check_budget", "approve_expense"]
    depends_on = ["check_budget"]

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
    domain = "finance"

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
            return safe_tool_error(e, "提交报销")


class ListExpensesTool(BaseTool):
    """查询报销记录"""

    name = "list_expenses"
    description = "查询报销记录列表，支持按状态和日期范围筛选"
    examples = [
        {"input": {}, "output_summary": "返回全部报销记录"},
        {"input": {"status": "pending"}, "output_summary": "返回待审批的报销记录"},
        {"input": {"start_date": "2026-03-01", "end_date": "2026-03-31"}, "output_summary": "返回本月的报销记录"},
    ]
    related_tools = ["submit_expense", "approve_expense", "check_budget"]
    gotchas = "状态可选值：pending/approved/rejected。不传筛选条件则返回全部记录。日期格式为YYYY-MM-DD。"

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
    domain = "finance"

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
            return safe_tool_error(e, "查询报销记录")


class ApproveExpenseTool(BaseTool):
    """审批报销单"""

    name = "approve_expense"
    description = "审批报销单，支持通过或驳回操作，需管理员权限"
    examples = [
        {"input": {"expense_id": "uuid-xxxx", "action": "approve", "comment": "符合报销标准"}, "output_summary": "通过报销单并添加审批意见"},
        {"input": {"expense_id": "uuid-xxxx", "action": "reject", "comment": "缺少发票附件"}, "output_summary": "驳回报销单并说明原因"},
    ]
    related_tools = ["list_expenses", "submit_expense", "check_budget"]
    gotchas = "expense_id和action均为必填。action仅支持approve和reject。此操作不可逆，需用户确认。需要admin权限。"

    required_role = "admin"
    is_irreversible = True  # HITL: 审批/驳回报销是不可逆财务操作

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
    domain = "finance"

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
            return safe_tool_error(e, "审批报销")


class CheckBudgetTool(BaseTool):
    """查询预算使用情况"""

    name = "check_budget"
    description = "查询预算使用情况，包括总额、已用、剩余和使用率"
    examples = [
        {"input": {}, "output_summary": "返回全组织的预算使用情况"},
        {"input": {"department_id": "uuid-xxxx", "period": "2026-03"}, "output_summary": "返回指定部门本月的预算使用情况"},
    ]
    related_tools = ["submit_expense", "list_expenses"]
    gotchas = "period格式为YYYY-MM。不传department_id则查全组织预算。建议在提交报销前先调用此工具确认预算余额。"

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
    domain = "finance"

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
            return safe_tool_error(e, "查询预算")
