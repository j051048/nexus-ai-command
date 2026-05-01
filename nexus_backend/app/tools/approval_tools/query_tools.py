import logging
import uuid
from typing import Any

import app.tools.approval_tools as _pkg

from ..base_tool import BaseTool

logger = logging.getLogger(__name__)


class GetEmployeeInfoTool(BaseTool):
    """AI助手查询员工信息"""

    name = "get_employee_info"
    description = (
        "根据员工姓名查询其基本信息和用户编号。当需要将姓名转换为员工编号时使用。"
    )
    required_role = "ai_assistant"
    examples = [
        {
            "input": {"query": "张三"},
            "output_summary": "返回匹配的员工列表，包含姓名、ID、部门",
        },
        {"input": {"query": "王"}, "output_summary": "返回所有姓王的员工列表"},
    ]
    related_tools = ["get_employee_approval_history", "get_employee_profile"]
    gotchas = (
        "不会返回老板（founder角色）的信息。模糊搜索可能匹配多个员工，需用户确认。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "员工姓名关键词"},
            "employee_name": {
                "type": "string",
                "description": "员工姓名（query的别名）",
            },
        },
        "required": ["query"],
    }
    domain = "hr"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        name = args.get("query") or args.get("employee_name")
        if not name:
            return self.format_result(data=None, summary="请提供员工姓名关键词")
        client = _pkg._get_client(config)
        result = (
            await client.table("users")
            .select("id, name, department, role")
            .ilike("name", f"%{name}%")
            .execute()
        )

        if not result.data:
            return self.format_result(data=None, summary=f"找不到名为 '{name}' 的员工")

        employees = [emp for emp in result.data if emp.get("role") != "founder"]

        if not employees:
            return self.format_result(
                data=None, summary=f"找不到名为 '{name}' 的普通员工"
            )

        return self.format_result(
            data=employees,
            summary=f"找到 {len(employees)} 名员工",
            actions=[
                {
                    "label": "查看审批历史",
                    "tool": "get_employee_approval_history",
                    "args": {"employee_id": employees[0]["id"]},
                },
            ],
        )


class GetEmployeeApprovalHistoryTool(BaseTool):
    """AI助手查询员工的审批历史"""

    name = "get_employee_approval_history"
    description = (
        "查询指定员工的审批申请历史记录。当用户说'审批记录'、'审批历史'时调用。"
    )
    required_role = "ai_assistant"
    examples = [
        {
            "input": {"employee_id": "a1b2c3d4-...", "limit": 5},
            "output_summary": "返回该员工最近5条审批记录，含状态、类型、金额",
        },
        {
            "input": {"employee_id": "a1b2c3d4-..."},
            "output_summary": "返回该员工最近5条审批记录（默认）",
        },
    ]
    related_tools = ["get_employee_info", "get_pending_approvals"]
    gotchas = "employee_id 必须是有效的 UUID 格式，传入姓名会报错。请先用 get_employee_info 通过姓名查询员工编号。"

    parameters = {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "string",
                "description": "员工ID（UUID格式），可通过 get_employee_info 工具查询获取",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "description": "返回记录数量，默认5条",
            },
        },
        "required": ["employee_id"],
    }
    domain = "approval"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        employee_id = args.get("employee_id")
        limit = args.get("limit", 5)

        # Validate UUID format
        try:
            uuid.UUID(employee_id)
        except (ValueError, AttributeError):
            return self.format_result(
                data=None,
                summary=f"employee_id '{employee_id}' 不是有效的UUID格式，请先使用 get_employee_info 工具通过姓名查询员工ID",
            )

        client = _pkg._get_client(config)
        result = (
            await client.table("approval_requests")
            .select("*")
            .eq("submitted_by", employee_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        if not result.data:
            return self.format_result(data=[], summary="该员工暂无审批记录")

        return self.format_result(
            data=result.data,
            summary=f"最近 {len(result.data)} 条审批记录",
            actions=[
                {
                    "label": "查看员工信息",
                    "tool": "get_employee_info",
                    "args": {"query": ""},
                },
                {"label": "查看待审批", "tool": "get_pending_approvals", "args": {}},
            ],
        )


class PendingApprovalsTool(BaseTool):
    name = "get_pending_approvals"
    description = "获取当前所有待处理的审批列表。当用户说'待审批'、'有什么要审的'、'审批列表'时调用。"
    examples = [
        {
            "input": {},
            "output_summary": "返回所有待处理审批单列表，含申请人、类型、金额、审批链步骤",
        },
    ]
    related_tools = [
        "approve_request",
        "reject_request",
        "get_employee_approval_history",
    ]
    gotchas = ""

    parameters = {"type": "object", "properties": {}, "required": []}
    domain = "approval"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _pkg._get_client(config)
        result = (
            await client.table("approval_requests")
            .select("*, users:submitted_by(name)")
            .eq("status", "pending")
            .execute()
        )
        if not result.data:
            return "当前没有任何待处理的审批。"
        items = []
        for item in result.data:
            user_name = item.get("users", {}).get("name", "未知用户")
            chain_info = ""
            if item.get("chain_id"):
                step = item.get("current_step", 0)
                level = item.get("approval_level", "")
                chain_info = f" [步骤{step + 1}/{level}]"
            items.append(
                f"ID: {item['id']}, 申请人: {user_name}, 类型: {item['type']}, "
                f"金额: ¥{item['amount']}, 描述: {item['description']}{chain_info}"
            )
        return "待处理清单：\n" + "\n".join(items)
