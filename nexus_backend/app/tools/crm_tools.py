"""
CRM 客户管理工具集
提供客户 CRUD、联系人管理、跟进记录、商机阶段推进、销售漏斗等完整功能。
所有工具通过 crm_service 操作 customers 表系统。
"""

import logging
from typing import Any

from app.services.crm_service import ACTIVITY_TYPES, CUSTOMER_STAGES, crm_service

from .base_tool import BaseTool
from ._shared import _get_client, _validate_uuid


logger = logging.getLogger(__name__)


def _get_org_id(config: dict = None) -> str | None:
    return config.get("org_id") if config else None


# ═══════════════════════════════════════════════════════════════════════════════
#  客户查询工具
# ═══════════════════════════════════════════════════════════════════════════════


class GetCustomersTool(BaseTool):
    """查询客户列表"""

    name = "get_customers"
    description = "查询CRM客户列表，支持按阶段筛选和关键词搜索。当用户说'查看客户'、'客户列表'、'有哪些客户'时调用。"

    parameters = {
        "type": "object",
        "properties": {
            "stage": {
                "type": "string",
                "description": f"客户阶段筛选: {', '.join(CUSTOMER_STAGES)}",
                "enum": list(CUSTOMER_STAGES),
            },
            "search": {
                "type": "string",
                "description": "按客户名称或公司名搜索",
            },
            "limit": {
                "type": "integer",
                "description": "返回数量限制，默认20",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        search = args.get("search")
        if search:
            customers = await crm_service.search_customers(org_id, search, db=client)
        else:
            filters = {}
            if args.get("stage"):
                filters["stage"] = args["stage"]
            if args.get("limit"):
                filters["limit"] = args["limit"]
            customers = await crm_service.list_customers(org_id, filters=filters or None, db=client)

        if not customers:
            return "当前暂无客户记录。您可以说「创建客户」来添加新客户。"

        stage_labels = {
            "lead": "线索",
            "prospect": "意向",
            "opportunity": "商机",
            "customer": "成交",
            "churned": "流失",
        }

        lines = [f"📋 共找到 {len(customers)} 位客户:\n"]
        for c in customers:
            stage = stage_labels.get(c.get("stage", ""), c.get("stage", ""))
            value = c.get("estimated_value") or 0
            value_str = f"¥{float(value):,.0f}" if value else "未评估"
            lines.append(
                f"- **{c.get('name', '未知')}** ({c.get('company', '')}) "
                f"| 阶段: {stage} | 预估金额: {value_str} | ID: {c['id'][:8]}..."
            )

        return "\n".join(lines)


class GetCustomerDetailTool(BaseTool):
    """查询客户详情"""

    name = "get_customer_detail"
    description = "查询指定客户的详细信息，包括联系人和最近跟进记录。当用户说'客户详情'、'查看某某客户'时调用。"

    parameters = {
        "type": "object",
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "客户ID",
            },
        },
        "required": ["customer_id"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        customer_id = args.get("customer_id", "")
        if not customer_id:
            return "❌ 请提供客户ID（customer_id）"
        if err := _validate_uuid(customer_id, "customer_id"):
            return f"❌ {err}"

        customer = await crm_service.get_customer(customer_id, db=client)
        if not customer:
            return f"❌ 未找到ID为 {customer_id} 的客户"

        contacts = await crm_service.list_contacts(customer_id, db=client)
        activities = await crm_service.get_activity_timeline(customer_id, limit=5, db=client)

        stage_labels = {
            "lead": "线索",
            "prospect": "意向",
            "opportunity": "商机",
            "customer": "成交",
            "churned": "流失",
        }

        value = customer.get("estimated_value") or 0
        lines = [
            f"## 客户详情: {customer.get('name', '未知')}",
            f"- 公司: {customer.get('company', '未填写')}",
            f"- 行业: {customer.get('industry', '未填写')}",
            f"- 阶段: {stage_labels.get(customer.get('stage', ''), customer.get('stage', ''))}",
            f"- 来源: {customer.get('source', '未填写')}",
            f"- 预估金额: ¥{float(value):,.0f}" if value else "- 预估金额: 未评估",
            f"- 创建时间: {str(customer.get('created_at', ''))[:10]}",
        ]

        if contacts:
            lines.append(f"\n### 联系人 ({len(contacts)}人)")
            for ct in contacts:
                primary = " ⭐主要" if ct.get("is_primary") else ""
                lines.append(
                    f"- {ct.get('name', '未知')}{primary} | {ct.get('title', '')} "
                    f"| 📞{ct.get('phone', '')} | 📧{ct.get('email', '')}"
                )

        if activities:
            type_labels = {
                "call": "电话",
                "email": "邮件",
                "meeting": "会议",
                "note": "备注",
                "deal_update": "商机更新",
            }
            lines.append(f"\n### 最近跟进 ({len(activities)}条)")
            for act in activities:
                t = type_labels.get(act.get("activity_type", ""), act.get("activity_type", ""))
                lines.append(f"- [{t}] {act.get('content', '')[:80]} ({str(act.get('created_at', ''))[:10]})")
        else:
            lines.append("\n### 最近跟进\n暂无跟进记录")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
#  客户创建/更新工具
# ═══════════════════════════════════════════════════════════════════════════════


class CreateCustomerTool(BaseTool):
    """创建新客户"""

    name = "create_customer"
    description = "在CRM中创建新客户记录。当用户说'添加客户'、'创建客户'、'录入新客户'时调用。"
    is_irreversible = True
    confirmation_message = "⚠️ 即将创建新客户记录，确认继续？"

    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "客户名称（必填）"},
            "company": {"type": "string", "description": "公司名称"},
            "industry": {"type": "string", "description": "所属行业"},
            "stage": {
                "type": "string",
                "description": f"客户阶段: {', '.join(CUSTOMER_STAGES)}，默认lead",
                "enum": list(CUSTOMER_STAGES),
            },
            "source": {"type": "string", "description": "客户来源（如：官网、展会、转介绍）"},
            "estimated_value": {"type": "number", "description": "预估成交金额"},
        },
        "required": ["name"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        name = args.get("name", "").strip()
        if not name:
            return "❌ 客户名称不能为空"

        # 预估金额校验
        estimated_value = args.get("estimated_value")
        if estimated_value is not None:
            try:
                estimated_value = float(estimated_value)
            except (TypeError, ValueError):
                return "❌ 预估金额格式错误，请提供有效的数字。"
            if estimated_value < 0:
                return "❌ 预估金额不能为负数。"

        data = {"name": name, "assigned_to": user_id}
        for field in ("company", "industry", "stage", "source", "estimated_value"):
            if args.get(field) is not None:
                data[field] = args[field]

        try:
            customer = await crm_service.create_customer(org_id, data, db=client)
        except Exception as e:
            return f"❌ 创建客户失败: {str(e)}"

        if not customer:
            return "❌ 创建客户失败，请稍后重试"

        return (
            f"✅ 客户创建成功！\n\n"
            f"- 名称: {customer.get('name')}\n"
            f"- 公司: {customer.get('company', '未填写')}\n"
            f"- 阶段: {customer.get('stage', 'lead')}\n"
            f"- ID: {customer['id']}\n\n"
            f"您可以继续添加联系人或跟进记录。"
        )


class UpdateCustomerTool(BaseTool):
    """更新客户信息"""

    name = "update_customer"
    description = "更新CRM中已有客户的信息。当用户说'更新客户'、'修改客户信息'时调用。"
    is_irreversible = True
    confirmation_message = "⚠️ 即将更新客户信息，确认继续？"

    parameters = {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "description": "客户ID（必填）"},
            "name": {"type": "string", "description": "客户名称"},
            "company": {"type": "string", "description": "公司名称"},
            "industry": {"type": "string", "description": "所属行业"},
            "stage": {"type": "string", "description": "客户阶段", "enum": CUSTOMER_STAGES},
            "source": {"type": "string", "description": "客户来源"},
            "estimated_value": {"type": "number", "description": "预估成交金额"},
        },
        "required": ["customer_id"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        customer_id = args.get("customer_id", "")
        if not customer_id:
            return "❌ 请提供客户ID（customer_id）"
        if err := _validate_uuid(customer_id, "customer_id"):
            return f"❌ {err}"

        data = {}
        for field in ("name", "company", "industry", "stage", "source", "estimated_value"):
            if args.get(field) is not None:
                data[field] = args[field]

        if not data:
            return "❌ 请提供至少一个要更新的字段"

        try:
            customer = await crm_service.update_customer(customer_id, data, db=client)
        except Exception as e:
            return f"❌ 更新客户失败: {str(e)}"

        if not customer:
            return f"❌ 未找到ID为 {customer_id} 的客户"

        updated_fields = ", ".join(f"{k}={v}" for k, v in data.items())
        return f"✅ 客户 {customer.get('name', '')} 已更新: {updated_fields}"


# ═══════════════════════════════════════════════════════════════════════════════
#  跟进记录工具
# ═══════════════════════════════════════════════════════════════════════════════


class AddFollowUpTool(BaseTool):
    """添加跟进记录"""

    name = "add_follow_up"
    description = (
        "为客户添加跟进记录（电话、邮件、会议、备注等）。当用户说'记录跟进'、'添加跟进'、'记一下拜访情况'时调用。"
    )
    is_irreversible = True
    confirmation_message = "⚠️ 即将添加跟进记录，确认继续？"

    parameters = {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "description": "客户ID（必填）"},
            "activity_type": {
                "type": "string",
                "description": f"跟进类型: {', '.join(ACTIVITY_TYPES)}",
                "enum": list(ACTIVITY_TYPES),
            },
            "content": {"type": "string", "description": "跟进内容（必填）"},
        },
        "required": ["customer_id", "activity_type", "content"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        customer_id = args.get("customer_id", "")
        activity_type = args.get("activity_type", "note")
        content = args.get("content", "")

        if not customer_id or not content:
            return "❌ 客户ID和跟进内容不能为空"
        if err := _validate_uuid(customer_id, "customer_id"):
            return f"❌ {err}"

        if activity_type not in ACTIVITY_TYPES:
            activity_type = "note"

        try:
            activity = await crm_service.create_activity(customer_id, activity_type, content, user_id, db=client)
        except Exception as e:
            return f"❌ 添加跟进记录失败: {str(e)}"

        if not activity:
            return "❌ 添加跟进记录失败，请确认客户ID是否正确"

        type_labels = {"call": "电话", "email": "邮件", "meeting": "会议", "note": "备注", "deal_update": "商机更新"}
        return f"✅ 跟进记录已添加: [{type_labels.get(activity_type, activity_type)}] {content[:80]}"


class GetFollowUpsTool(BaseTool):
    """查询跟进记录"""

    name = "get_follow_ups"
    description = "查询客户的跟进记录时间线。当用户说'跟进记录'、'历史跟进'、'拜访记录'时调用。"

    parameters = {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "description": "客户ID（必填）"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "description": "返回数量限制，默认20"},
        },
        "required": ["customer_id"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        customer_id = args.get("customer_id", "")
        limit = args.get("limit", 20)
        if not customer_id:
            return "❌ 请提供客户ID（customer_id）"

        # Validate UUID format
        try:
            _uuid.UUID(customer_id)
        except (ValueError, TypeError, AttributeError):
            return f"customer_id '{customer_id}' 不是有效的UUID格式，请检查客户ID。"

        # Clamp limit to safe range
        try:
            limit = max(1, min(int(limit), 100))
        except (TypeError, ValueError):
            limit = 20

        activities = await crm_service.get_activity_timeline(customer_id, limit=limit, db=client)
        if not activities:
            return "暂无跟进记录。您可以说「添加跟进」来记录新的跟进。"

        type_labels = {
            "call": "📞电话",
            "email": "📧邮件",
            "meeting": "🤝会议",
            "note": "📝备注",
            "deal_update": "💰商机更新",
        }

        lines = [f"📋 跟进记录 (共{len(activities)}条):\n"]
        for act in activities:
            t = type_labels.get(act.get("activity_type", ""), act.get("activity_type", ""))
            date = str(act.get("created_at", ""))[:10]
            lines.append(f"- {date} [{t}] {act.get('content', '')[:100]}")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
#  商机阶段 / 销售漏斗工具
# ═══════════════════════════════════════════════════════════════════════════════


class UpdateCustomerStageTool(BaseTool):
    """推进客户阶段"""

    name = "update_customer_stage"
    description = (
        "推进或变更客户的销售阶段（线索→意向→商机→成交/流失）。"
        "当用户说'推进商机'、'客户成交了'、'客户流失了'、'变更阶段'时调用。"
    )
    is_irreversible = True
    confirmation_message = "⚠️ 即将变更客户阶段，确认继续？"

    parameters = {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "description": "客户ID（必填）"},
            "new_stage": {
                "type": "string",
                "description": f"新阶段: {', '.join(CUSTOMER_STAGES)}",
                "enum": list(CUSTOMER_STAGES),
            },
        },
        "required": ["customer_id", "new_stage"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        customer_id = args.get("customer_id", "")
        new_stage = args.get("new_stage", "")

        if not customer_id or not new_stage:
            return "❌ 客户ID和新阶段不能为空"
        if err := _validate_uuid(customer_id, "customer_id"):
            return f"❌ {err}"

        if new_stage not in CUSTOMER_STAGES:
            return f"❌ 无效的阶段: {new_stage}，可选: {', '.join(CUSTOMER_STAGES)}"

        old_customer = await crm_service.get_customer(customer_id, db=client)
        if not old_customer:
            return f"❌ 未找到ID为 {customer_id} 的客户"

        old_stage = old_customer.get("stage", "unknown")

        try:
            customer = await crm_service.update_customer(customer_id, {"stage": new_stage}, db=client)
        except Exception as e:
            return f"❌ 阶段变更失败: {str(e)}"

        # 记录阶段变更活动
        await crm_service.create_activity(
            customer_id,
            "deal_update",
            f"阶段变更: {old_stage} → {new_stage}",
            user_id,
            db=client,
        )

        # Emit business events for downstream handlers
        try:
            from app.services.event_bus import EventType, event_bus

            event_data = {
                "customer_id": customer_id,
                "customer_name": customer.get("name", ""),
                "old_stage": old_stage,
                "new_stage": new_stage,
                "user_id": user_id,
            }
            if new_stage == "customer":
                await event_bus.emit(EventType.DEAL_WON.value, event_data)
            elif new_stage == "opportunity":
                await event_bus.emit(EventType.LEAD_QUALIFIED.value, event_data)
        except Exception as e:
            logger.debug(f"Event emission failed: {e}")

        stage_labels = {
            "lead": "线索",
            "prospect": "意向",
            "opportunity": "商机",
            "customer": "成交",
            "churned": "流失",
        }

        return (
            f"✅ 客户 {customer.get('name', '')} 阶段已更新: "
            f"{stage_labels.get(old_stage, old_stage)} → {stage_labels.get(new_stage, new_stage)}"
        )


class GetSalesPipelineTool(BaseTool):
    """获取销售漏斗视图"""

    name = "get_sales_pipeline"
    description = (
        "获取销售漏斗/管道视图，展示各阶段客户数量和金额分布。当用户说'销售漏斗'、'管道视图'、'各阶段情况'时调用。"
    )

    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        stats = await crm_service.get_customer_stats(org_id, db=client)
        if not stats or stats.get("total_customers", 0) == 0:
            return "当前暂无客户数据。您可以说「创建客户」来添加新客户。"

        # stage_distribution is a list of {stage, name, count, color} — convert to dict
        stage_dist_list = stats.get("stage_distribution", [])
        stage_dist = (
            {item["stage"]: item["count"] for item in stage_dist_list}
            if isinstance(stage_dist_list, list)
            else stage_dist_list
        )
        stage_labels = {
            "lead": "🔵 线索",
            "prospect": "🟡 意向",
            "opportunity": "🟠 商机",
            "customer": "🟢 成交",
            "churned": "🔴 流失",
        }

        # 获取各阶段金额
        all_customers = await crm_service.list_customers(org_id, db=client)
        stage_values = {}
        for c in all_customers or []:
            s = c.get("stage", "lead")
            v = float(c.get("estimated_value") or 0)
            stage_values[s] = stage_values.get(s, 0) + v

        lines = [
            "## 📊 销售漏斗概览\n",
            f"- 客户总数: **{stats.get('total_customers', 0)}**",
            f"- 本月新增: **{stats.get('new_this_month', 0)}**",
            f"- 转化率: **{stats.get('conversion_rate', 0):.1f}%**",
            f"- 总预估金额: **¥{float(stats.get('total_estimated_value', 0)):,.0f}**",
            "",
            "### 各阶段分布\n",
            "| 阶段 | 客户数 | 预估金额 |",
            "| --- | --- | --- |",
        ]

        for stage_key in ("lead", "prospect", "opportunity", "customer", "churned"):
            count = stage_dist.get(stage_key, 0)
            value = stage_values.get(stage_key, 0)
            label = stage_labels.get(stage_key, stage_key)
            lines.append(f"| {label} | {count} | ¥{value:,.0f} |")

        return "\n".join(lines)
