"""
审批流管理工具集
提供审批流模板查询和创建功能
"""

import logging
from typing import Any

from app.services.approval_flow_service import approval_flow_service
from app.tools._shared import safe_tool_error

from ._shared import _get_client
from .base_tool import BaseTool

logger = logging.getLogger(__name__)


def _get_org_id(config: dict = None) -> str | None:
    return config.get("org_id") if config else None


# ============================================================================
# 审批流管理工具
# ============================================================================


class ListApprovalFlowsTool(BaseTool):
    """查询审批流模板列表"""

    name = "list_approval_flows"
    description = "查询当前组织的审批流模板列表。当用户说'查看审批流'、'审批流列表'时调用。可按触发类型筛选。"
    examples = [
        {"input": {}, "output_summary": "返回组织下所有审批流模板，含名称、触发类型、步骤数、状态"},
        {"input": {"trigger_type": "expense"}, "output_summary": "返回报销类型的审批流模板列表"},
    ]
    related_tools = ["create_approval_flow"]
    gotchas = "必须已登录且有组织信息，否则会返回错误。"

    parameters = {
        "type": "object",
        "properties": {
            "trigger_type": {
                "type": "string",
                "description": "触发类型（可选，如: leave/expense/asset/work_order）",
            },
        },
        "required": [],
    }
    domain = "approval"

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        trigger_type = args.get("trigger_type")

        try:
            flows = await approval_flow_service.list_approval_flows(
                org_id=org_id,
                trigger_type=trigger_type,
                db=client,
            )

            if not flows:
                return "📋 当前暂无审批流模板。"

            trigger_labels = {
                "leave": "请假审批",
                "expense": "报销审批",
                "asset": "资产审批",
                "work_order": "工单审批",
            }

            lines = [f"📋 共找到 {len(flows)} 个审批流模板:\n"]
            for flow in flows:
                ttype = trigger_labels.get(flow.get("trigger_type", ""), flow.get("trigger_type", ""))
                steps_count = len(flow.get("steps", []))
                is_active = "启用" if flow.get("is_active") else "停用"
                lines.append(
                    f"- **{flow.get('name', '未知')}** | 触发类型: {ttype} | "
                    f"步骤数: {steps_count} | 状态: {is_active} | "
                    f"ID: {flow['id'][:8]}..."
                )

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"查询审批流列表失败: {e}")
            return safe_tool_error(e, "查询审批流列表")


class CreateApprovalFlowTool(BaseTool):
    """创建审批流模板"""

    name = "create_approval_flow"
    description = "创建新的审批流模板。当用户说'创建审批流'、'配置审批流程'时调用。需要管理员权限。"
    required_role = "admin"
    examples = [
        {
            "input": {
                "name": "请假审批流",
                "trigger_type": "leave",
                "steps": [{"approver_role": "manager"}, {"approver_role": "director"}],
            },
            "output_summary": "创建包含两步审批的请假审批流模板",
        },
        {
            "input": {
                "name": "大额报销审批",
                "trigger_type": "expense",
                "steps": [{"approver_role": "manager"}, {"approver_role": "cfo"}],
            },
            "output_summary": "创建报销审批流模板",
        },
    ]
    related_tools = ["list_approval_flows"]
    gotchas = "需要管理员权限。steps 必须为非空数组。name 最大长度100字符。trigger_type 仅支持 leave/expense/asset/work_order 四种。"

    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "审批流名称",
                "maxLength": 100,
            },
            "trigger_type": {
                "type": "string",
                "description": "触发类型",
                "enum": ["leave", "expense", "asset", "work_order"],
            },
            "steps": {
                "type": "array",
                "description": "审批步骤JSON数组",
                "items": {"type": "object"},
            },
        },
        "required": ["name", "trigger_type", "steps"],
    }
    domain = "approval"

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        name = args.get("name", "").strip()
        trigger_type = args.get("trigger_type", "").strip()
        steps = args.get("steps")

        if not name or not trigger_type:
            return "❌ 审批流名称和触发类型不能为空"
        if not steps or not isinstance(steps, list):
            return "❌ 审批步骤不能为空，必须为数组格式"

        try:
            flow = await approval_flow_service.create_approval_flow(
                org_id=org_id,
                name=name,
                trigger_type=trigger_type,
                steps=steps,
                db=client,
            )

            trigger_labels = {
                "leave": "请假审批",
                "expense": "报销审批",
                "asset": "资产审批",
                "work_order": "工单审批",
            }
            ttype = trigger_labels.get(trigger_type, trigger_type)

            return (
                f"✅ 审批流创建成功！\n\n"
                f"- 名称: {name}\n"
                f"- 触发类型: {ttype}\n"
                f"- 审批步骤数: {len(steps)}\n"
                f"- ID: {flow['id']}"
            )

        except Exception as e:
            logger.error(f"创建审批流失败: {e}")
            return safe_tool_error(e, "创建审批流")
