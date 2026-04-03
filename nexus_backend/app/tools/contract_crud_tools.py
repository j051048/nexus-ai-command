"""
合同 CRUD 工具集
提供合同查询、创建、到期提醒等功能。
所有工具通过 contract_service 操作 contracts 表。
"""

import logging
import uuid as _uuid
from typing import Any

from app.services.contract_service import contract_service
from app.tools._shared import safe_tool_error

from ._shared import _get_client
from .base_tool import BaseTool

logger = logging.getLogger(__name__)


def _get_org_id(config: dict = None) -> str | None:
    return config.get("org_id") if config else None


# ═══════════════════════════════════════════════════════════════════════════════
#  合同查询工具
# ═══════════════════════════════════════════════════════════════════════════════


class GetContractsTool(BaseTool):
    """查询合同列表"""

    name = "get_contracts"
    domain = "crm"
    description = "查询合同列表，支持按状态筛选和关键词搜索"
    examples = [
        {"input": {}, "output_summary": "返回全部合同列表"},
        {"input": {"status": "active"}, "output_summary": "返回所有生效中的合同"},
        {"input": {"search": "服务协议"}, "output_summary": "按标题搜索包含'服务协议'的合同"},
    ]
    gotchas = "status可选值: draft/pending_review/active/expired/terminated/renewed。不传则返回全部。"
    related_tools = ["create_contract", "get_expiring_contracts"]

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
    domain = "crm"
    description = "创建新合同记录，支持设置类型、金额、日期和关联客户"
    examples = [
        {"input": {"title": "华为年度服务合同", "contract_type": "service", "amount": 100000}, "output_summary": "创建一份金额10万的服务合同（草稿状态）"},
        {"input": {"title": "保密协议", "customer_id": "uuid-xxxx", "start_date": "2026-01-01", "end_date": "2027-01-01"}, "output_summary": "创建关联客户的保密协议并设置有效期"},
    ]
    is_irreversible = True
    confirmation_message = "⚠️ 即将创建新合同记录，确认继续？"
    gotchas = "start_date和end_date格式为YYYY-MM-DD，end_date不能早于start_date。amount必须大于0。customer_id必须是已存在的有效UUID。status默认为draft。"
    related_tools = ["get_contracts", "get_expiring_contracts", "analyze_contract"]

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
        from datetime import datetime

        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        title = args.get("title", "").strip()
        if not title:
            return "❌ 合同标题不能为空"

        # ── 输入校验 ──
        # 金额校验
        amount = args.get("amount")
        if amount is not None:
            try:
                amount = float(amount)
            except (TypeError, ValueError):
                return "❌ 合同金额格式错误，请提供有效的数字。"
            if amount <= 0:
                return "❌ 合同金额必须大于0。"

        # 日期校验
        start_date = args.get("start_date")
        end_date = args.get("end_date")
        if start_date or end_date:
            try:
                s = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
                e = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None
                if s and e and e < s:
                    return "❌ 合同结束日期不能早于开始日期。"
            except ValueError:
                return "❌ 日期格式错误，请使用 YYYY-MM-DD 格式。"

        # customer_id 存在性校验
        customer_id = args.get("customer_id")
        if customer_id:
            # Validate UUID format
            try:
                _uuid.UUID(customer_id)
            except (ValueError, TypeError, AttributeError):
                return f"❌ customer_id '{customer_id}' 不是有效的UUID格式。"

            try:
                cust_res = await client.table("customers").select("id").eq("id", customer_id).maybe_single().execute()
                if not cust_res.data:
                    return f"❌ 客户 ID {customer_id} 不存在，请先创建客户。"
            except Exception:
                pass  # 校验失败不阻塞，让 service 层兜底

        data = {"title": title, "created_by": user_id}
        for field in ("customer_id", "contract_type", "amount", "start_date", "end_date"):
            if args.get(field) is not None:
                data[field] = args[field]

        try:
            contract = await contract_service.create_contract(org_id, data, db=client)
        except Exception as e:
            return safe_tool_error(e, "创建合同")

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
    domain = "crm"
    description = "查询指定天数内即将到期的合同，方便提前续约处理"
    examples = [
        {"input": {}, "output_summary": "返回未来30天内即将到期的合同列表"},
        {"input": {"days": 7}, "output_summary": "返回未来7天内即将到期的合同列表"},
    ]
    gotchas = "days范围1-365，默认30天。只返回状态为active的合同。无到期合同时返回提示信息。"
    related_tools = ["get_contracts", "create_contract"]

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
                f"- **{c.get('title', '未命名')}** | 到期日: {end_date} | 金额: {amount_str} | ID: {c['id'][:8]}..."
            )

        lines.append("\n💡 建议提前安排续约或处理事宜。")
        return "\n".join(lines)
