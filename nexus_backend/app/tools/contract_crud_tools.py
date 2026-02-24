"""
合同 CRUD 工具集
提供合同查询、创建、到期提醒等功能。
所有工具通过 contract_service 操作 contracts 表。
"""

import logging
from typing import Any

from app.core.database import supabase
from app.services.contract_service import contract_service

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


def _get_client(config: dict = None):
    """Get scoped DB client if user token available, else fallback to service client."""
    token = config.get("token") if config else None
    return supabase.get_scoped_client(token) if token and supabase else supabase


def _get_org_id(config: dict = None) -> str | None:
    return config.get("org_id") if config else None


# ═══════════════════════════════════════════════════════════════════════════════
#  合同查询工具
# ═══════════════════════════════════════════════════════════════════════════════


class GetContractsTool(BaseTool):
    """查询合同列表"""

    name = "get_contracts"
    description = "查询合同列表，支持按状态和关键词筛选。" "当用户说'查看合同'、'合同列表'、'有哪些合同'时调用。"

    parameters = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "合同状态: draft, pending_review, active, expired, terminated, renewed",
                "enum": [
                    "draft",
                    "pending_review",
                    "active",
                    "expired",
                    "terminated",
                    "renewed",
                ],
            },
            "search": {
                "type": "string",
                "description": "按合同标题搜索",
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
        if args.get("search"):
            filters["search"] = args["search"]

        contracts = await contract_service.list_contracts(org_id, filters=filters or None, db=client)

        if not contracts:
            return "当前暂无合同记录。您可以说「创建合同」来添加新合同。"

        status_labels = {
            "draft": "草稿",
            "pending_review": "审核中",
            "active": "生效中",
            "expired": "已过期",
            "terminated": "已终止",
            "renewed": "已续约",
        }

        lines = [f"📋 共找到 {len(contracts)} 份合同:\n"]
        for c in contracts:
            status = status_labels.get(c.get("status", ""), c.get("status", ""))
            amount = c.get("amount") or 0
            amount_str = f"¥{float(amount):,.0f}" if amount else "未填写"
            end_date = str(c.get("end_date", ""))[:10] if c.get("end_date") else "未设定"
            lines.append(
                f"- **{c.get('title', '未命名')}** | 状态: {status} "
                f"| 金额: {amount_str} | 到期: {end_date} "
                f"| ID: {c['id'][:8]}..."
            )

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
#  合同创建工具
# ═══════════════════════════════════════════════════════════════════════════════


class CreateContractTool(BaseTool):
    """创建新合同"""

    name = "create_contract"
    description = "在系统中创建新合同记录。" "当用户说'创建合同'、'新建合同'、'录入合同'时调用。"
    is_irreversible = True
    confirmation_message = "⚠️ 即将创建新合同记录，确认继续？"

    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "合同标题（必填）"},
            "customer_id": {"type": "string", "description": "关联客户ID"},
            "contract_type": {
                "type": "string",
                "description": "合同类型: sales, purchase, service, nda, other",
                "enum": ["sales", "purchase", "service", "nda", "other"],
            },
            "amount": {"type": "number", "description": "合同金额"},
            "start_date": {"type": "string", "description": "开始日期 (YYYY-MM-DD)"},
            "end_date": {"type": "string", "description": "结束日期 (YYYY-MM-DD)"},
        },
        "required": ["title"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        title = args.get("title", "").strip()
        if not title:
            return "❌ 合同标题不能为空"

        data = {"title": title, "created_by": user_id}
        for field in ("customer_id", "contract_type", "amount", "start_date", "end_date"):
            if args.get(field) is not None:
                data[field] = args[field]

        try:
            contract = await contract_service.create_contract(org_id, data, db=client)
        except Exception as e:
            return f"❌ 创建合同失败: {str(e)}"

        if not contract:
            return "❌ 创建合同失败，请稍后重试"

        type_labels = {
            "sales": "销售合同",
            "purchase": "采购合同",
            "service": "服务合同",
            "nda": "保密协议",
            "other": "其他",
        }
        ctype = type_labels.get(contract.get("contract_type", ""), contract.get("contract_type", ""))

        return (
            f"✅ 合同创建成功！\n\n"
            f"- 标题: {contract.get('title')}\n"
            f"- 类型: {ctype}\n"
            f"- 状态: 草稿\n"
            f"- ID: {contract['id']}\n\n"
            f"您可以继续更新合同详情或关联客户。"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  到期合同提醒工具
# ═══════════════════════════════════════════════════════════════════════════════


class GetExpiringContractsTool(BaseTool):
    """查询即将到期的合同"""

    name = "get_expiring_contracts"
    description = (
        "查询即将到期的合同，方便提前续约或处理。" "当用户说'到期合同'、'合同到期提醒'、'哪些合同快到期了'时调用。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "查看未来多少天内到期的合同，默认30天",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        days = args.get("days", 30)
        days = min(max(1, days), 365)

        contracts = await contract_service.get_expiring_contracts(org_id, days=days, db=client)

        if not contracts:
            return f"未来 {days} 天内没有即将到期的合同。"

        lines = [f"⏰ 未来 {days} 天内有 {len(contracts)} 份合同即将到期:\n"]
        for c in contracts:
            amount = c.get("amount") or 0
            amount_str = f"¥{float(amount):,.0f}" if amount else "未填写"
            end_date = str(c.get("end_date", ""))[:10]
            lines.append(
                f"- **{c.get('title', '未命名')}** | 到期日: {end_date} " f"| 金额: {amount_str} | ID: {c['id'][:8]}..."
            )

        lines.append("\n💡 建议提前安排续约或处理事宜。")
        return "\n".join(lines)
