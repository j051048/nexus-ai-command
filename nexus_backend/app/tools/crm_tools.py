"""
CRM 客户管理工具集
提供客户 CRUD、联系人管理、跟进记录、商机阶段推进、销售漏斗等完整功能。
所有工具通过 crm_service 操作 customers 表系统。
"""

import logging
from typing import Any

from app.services.crm_service import ACTIVITY_TYPES, CUSTOMER_STAGES, crm_service
from app.tools._shared import safe_tool_error
from app.tools.registry import register_tool

from ._shared import _get_client, _validate_uuid
from .base_tool import BaseTool

logger = logging.getLogger(__name__)


def _get_org_id(config: dict = None) -> str | None:
    return config.get("org_id") if config else None


# ═══════════════════════════════════════════════════════════════════════════════
#  客户查询工具
# ═══════════════════════════════════════════════════════════════════════════════


@register_tool(name="get_customers", category="crm", description="查询客户列表")
class GetCustomersTool(BaseTool):
    """查询客户列表"""

    name = "get_customers"
    description = "查询客户列表，支持按阶段筛选和关键词搜索"
    examples = [
        {"input": {}, "output_summary": "返回全部客户列表（默认最多20条）"},
        {
            "input": {"stage": "opportunity", "limit": 10},
            "output_summary": "返回商机阶段的前10位客户",
        },
        {
            "input": {"search": "华为"},
            "output_summary": "按名称或公司名搜索包含'华为'的客户",
        },
    ]
    gotchas = "stage参数可选值: lead/prospect/customer/churned。不传则返回全部。结果按updated_at倒序，默认limit=20。"
    related_tools = ["get_customer_detail", "get_sales_pipeline", "create_customer"]

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
    domain = "crm"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return self.format_result(data=None, summary="无法获取组织信息，请确保已正确登录")

        search = args.get("search")
        if search:
            customers = await crm_service.search_customers(org_id, search, db=client)
        else:
            filters = {}
            if args.get("stage"):
                filters["stage"] = args["stage"]
            if args.get("limit"):
                filters["limit"] = args["limit"]
            customers = await crm_service.list_customers(
                org_id, filters=filters or None, db=client
            )

        if not customers:
            return self.format_result(
                data=[],
                summary="当前暂无客户记录",
                actions=[{"label": "创建客户", "tool": "create_customer", "args": {}}],
            )

        return self.format_result(
            data=customers,
            summary=f"共找到 {len(customers)} 位客户",
            actions=[
                {"label": "查看详情", "tool": "get_customer_detail", "args": {"customer_id": customers[0]["id"]}},
                {"label": "查看销售漏斗", "tool": "get_sales_pipeline", "args": {}},
                {"label": "创建客户", "tool": "create_customer", "args": {}},
            ],
        )


class GetCustomerDetailTool(BaseTool):
    """查询客户详情"""

    name = "get_customer_detail"
    description = "查询指定客户的详细信息，包括联系人和最近跟进记录"
    examples = [
        {
            "input": {"customer_id": "uuid-xxxx"},
            "output_summary": "返回客户基本信息、联系人列表和最近5条跟进记录",
        },
    ]
    gotchas = "customer_id必须是有效的UUID格式，否则报错。返回的跟进记录默认最多5条。"
    related_tools = ["get_customers", "get_follow_ups", "update_customer"]

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
    domain = "crm"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        customer_id = args.get("customer_id", "")
        if not customer_id:
            return self.format_result(data=None, summary="请提供客户ID（customer_id）")
        if err := _validate_uuid(customer_id, "customer_id"):
            return self.format_result(data=None, summary=err)

        customer = await crm_service.get_customer(customer_id, db=client)
        if not customer:
            return self.format_result(data=None, summary=f"未找到ID为 {customer_id} 的客户")

        contacts = await crm_service.list_contacts(customer_id, db=client)
        activities = await crm_service.get_activity_timeline(
            customer_id, limit=5, db=client
        )

        detail = {
            **customer,
            "contacts": contacts or [],
            "recent_activities": activities or [],
        }

        return self.format_result(
            data=detail,
            summary=f"客户 {customer.get('name', '未知')} 的详细信息",
            actions=[
                {"label": "查看跟进记录", "tool": "get_follow_ups", "args": {"customer_id": customer_id}},
                {"label": "更新客户", "tool": "update_customer", "args": {"customer_id": customer_id}},
            ],
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  客户创建/更新工具
# ═══════════════════════════════════════════════════════════════════════════════


class CreateCustomerTool(BaseTool):
    """创建新客户"""

    name = "create_customer"
    description = "创建新客户记录，支持设置阶段、来源和预估金额"
    examples = [
        {
            "input": {"name": "张三", "company": "华为", "stage": "lead"},
            "output_summary": "创建名为张三的线索阶段客户",
        },
        {
            "input": {"name": "李四", "source": "展会", "estimated_value": 50000},
            "output_summary": "创建来源为展会、预估金额5万的客户",
        },
    ]
    gotchas = "name为必填字段。estimated_value不能为负数。stage默认为lead。创建后自动将assigned_to设为当前用户。"
    related_tools = ["get_customers", "update_customer", "add_follow_up"]
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
            "source": {
                "type": "string",
                "description": "客户来源（如：官网、展会、转介绍）",
            },
            "estimated_value": {"type": "number", "description": "预估成交金额"},
        },
        "required": ["name"],
    }
    domain = "crm"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return self.format_result(data=None, summary="无法获取组织信息，请确保已正确登录")

        name = args.get("name", "").strip()
        if not name:
            return self.format_result(data=None, summary="客户名称不能为空")

        # 预估金额校验
        estimated_value = args.get("estimated_value")
        if estimated_value is not None:
            try:
                estimated_value = float(estimated_value)
            except (TypeError, ValueError):
                return self.format_result(data=None, summary="预估金额格式错误，请提供有效的数字")
            if estimated_value < 0:
                return self.format_result(data=None, summary="预估金额不能为负数")

        data = {"name": name, "assigned_to": user_id}
        for field in ("company", "industry", "stage", "source", "estimated_value"):
            if args.get(field) is not None:
                data[field] = args[field]

        try:
            customer = await crm_service.create_customer(org_id, data, db=client)
        except Exception as e:
            return safe_tool_error(e, "创建客户")

        if not customer:
            return self.format_result(data=None, summary="创建客户失败，请稍后重试")

        return self.format_result(
            data=customer,
            summary=f"客户 {customer.get('name')} 创建成功",
            actions=[
                {"label": "查看详情", "tool": "get_customer_detail", "args": {"customer_id": customer["id"]}},
                {"label": "更新客户", "tool": "update_customer", "args": {"customer_id": customer["id"]}},
                {"label": "添加跟进", "tool": "add_follow_up", "args": {"customer_id": customer["id"]}},
            ],
        )


class UpdateCustomerTool(BaseTool):
    """更新客户信息"""

    name = "update_customer"
    description = "更新已有客户的信息，支持修改名称、公司、阶段等字段"
    examples = [
        {
            "input": {"customer_id": "uuid-xxxx", "company": "新公司名"},
            "output_summary": "更新指定客户的公司名称",
        },
        {
            "input": {
                "customer_id": "uuid-xxxx",
                "stage": "customer",
                "estimated_value": 100000,
            },
            "output_summary": "同时更新客户阶段和预估金额",
        },
    ]
    gotchas = "customer_id必须是有效UUID。至少提供一个要更新的字段，否则报错。不会自动记录阶段变更活动，推进阶段请用update_customer_stage。"
    related_tools = ["get_customer_detail", "update_customer_stage", "create_customer"]
    is_irreversible = True
    confirmation_message = "⚠️ 即将更新客户信息，确认继续？"

    parameters = {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "description": "客户ID（必填）"},
            "name": {"type": "string", "description": "客户名称"},
            "company": {"type": "string", "description": "公司名称"},
            "industry": {"type": "string", "description": "所属行业"},
            "stage": {
                "type": "string",
                "description": "客户阶段",
                "enum": CUSTOMER_STAGES,
            },
            "source": {"type": "string", "description": "客户来源"},
            "estimated_value": {"type": "number", "description": "预估成交金额"},
        },
        "required": ["customer_id"],
    }
    domain = "crm"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        customer_id = args.get("customer_id", "")
        if not customer_id:
            return self.format_result(data=None, summary="请提供客户ID（customer_id）")
        if err := _validate_uuid(customer_id, "customer_id"):
            return self.format_result(data=None, summary=err)

        data = {}
        for field in (
            "name",
            "company",
            "industry",
            "stage",
            "source",
            "estimated_value",
        ):
            if args.get(field) is not None:
                data[field] = args[field]

        if not data:
            return self.format_result(data=None, summary="请提供至少一个要更新的字段")

        try:
            customer = await crm_service.update_customer(customer_id, data, db=client)
        except Exception as e:
            return safe_tool_error(e, "更新客户")

        if not customer:
            return self.format_result(data=None, summary=f"未找到ID为 {customer_id} 的客户")

        updated_fields = ", ".join(f"{k}={v}" for k, v in data.items())
        return self.format_result(
            data=customer,
            summary=f"客户 {customer.get('name', '')} 已更新: {updated_fields}",
            actions=[
                {"label": "查看详情", "tool": "get_customer_detail", "args": {"customer_id": customer_id}},
                {"label": "推进阶段", "tool": "update_customer_stage", "args": {"customer_id": customer_id}},
            ],
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  跟进记录工具
# ═══════════════════════════════════════════════════════════════════════════════


class AddFollowUpTool(BaseTool):
    """添加跟进记录"""

    name = "add_follow_up"
    description = "为指定客户添加跟进记录，支持电话、邮件、会议、备注等类型"
    examples = [
        {
            "input": {
                "customer_id": "uuid-xxxx",
                "activity_type": "call",
                "content": "电话沟通了产品报价",
            },
            "output_summary": "为客户添加一条电话跟进记录",
        },
        {
            "input": {
                "customer_id": "uuid-xxxx",
                "activity_type": "meeting",
                "content": "现场拜访讨论合作方案",
            },
            "output_summary": "为客户添加一条会议跟进记录",
        },
    ]
    is_irreversible = True
    confirmation_message = "⚠️ 即将添加跟进记录，确认继续？"
    gotchas = "customer_id必须是有效UUID。activity_type无效时自动降级为note。content不能为空。"
    related_tools = ["get_follow_ups", "get_customer_detail", "update_customer_stage"]

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
    domain = "crm"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        customer_id = args.get("customer_id", "")
        activity_type = args.get("activity_type", "note")
        content = args.get("content", "")

        if not customer_id or not content:
            return self.format_result(data=None, summary="客户ID和跟进内容不能为空")
        if err := _validate_uuid(customer_id, "customer_id"):
            return self.format_result(data=None, summary=err)

        if activity_type not in ACTIVITY_TYPES:
            activity_type = "note"

        try:
            activity = await crm_service.create_activity(
                customer_id, activity_type, content, user_id, db=client
            )
        except Exception as e:
            return safe_tool_error(e, "添加跟进记录")

        if not activity:
            return self.format_result(data=None, summary="添加跟进记录失败，请确认客户ID是否正确")

        type_labels = {
            "call": "电话",
            "email": "邮件",
            "meeting": "会议",
            "note": "备注",
            "deal_update": "商机更新",
        }
        return self.format_result(
            data=activity,
            summary=f"跟进记录已添加: [{type_labels.get(activity_type, activity_type)}] {content[:80]}",
            actions=[
                {"label": "查看跟进记录", "tool": "get_follow_ups", "args": {"customer_id": customer_id}},
                {"label": "查看客户详情", "tool": "get_customer_detail", "args": {"customer_id": customer_id}},
                {"label": "推进阶段", "tool": "update_customer_stage", "args": {"customer_id": customer_id}},
            ],
        )


class GetFollowUpsTool(BaseTool):
    """查询跟进记录"""

    name = "get_follow_ups"
    description = "查询指定客户的跟进记录时间线，按时间倒序排列"
    examples = [
        {
            "input": {"customer_id": "uuid-xxxx"},
            "output_summary": "返回该客户最近20条跟进记录",
        },
        {
            "input": {"customer_id": "uuid-xxxx", "limit": 5},
            "output_summary": "返回该客户最近5条跟进记录",
        },
    ]
    gotchas = (
        "customer_id必须是有效UUID。limit范围1-100，默认20。无效limit值自动回退为20。"
    )
    related_tools = ["add_follow_up", "get_customer_detail"]

    parameters = {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "description": "客户ID（必填）"},
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "description": "返回数量限制，默认20",
            },
        },
        "required": ["customer_id"],
    }
    domain = "crm"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        customer_id = args.get("customer_id", "")
        limit = args.get("limit", 20)
        if not customer_id:
            return self.format_result(data=None, summary="请提供客户ID（customer_id）")

        if err := _validate_uuid(customer_id, "customer_id"):
            return self.format_result(data=None, summary=err)

        # Clamp limit to safe range
        try:
            limit = max(1, min(int(limit), 100))
        except (TypeError, ValueError):
            limit = 20

        activities = await crm_service.get_activity_timeline(
            customer_id, limit=limit, db=client
        )
        if not activities:
            return self.format_result(
                data=[],
                summary="暂无跟进记录",
                actions=[{"label": "添加跟进", "tool": "add_follow_up", "args": {"customer_id": customer_id}}],
            )

        return self.format_result(
            data=activities,
            summary=f"共 {len(activities)} 条跟进记录",
            actions=[
                {"label": "添加跟进", "tool": "add_follow_up", "args": {"customer_id": customer_id}},
                {"label": "查看客户详情", "tool": "get_customer_detail", "args": {"customer_id": customer_id}},
            ],
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  商机阶段 / 销售漏斗工具
# ═══════════════════════════════════════════════════════════════════════════════


class UpdateCustomerStageTool(BaseTool):
    """推进客户阶段"""

    name = "update_customer_stage"
    description = "推进或变更客户的销售阶段，自动记录阶段变更活动并触发业务事件"
    examples = [
        {
            "input": {"customer_id": "uuid-xxxx", "new_stage": "opportunity"},
            "output_summary": "将客户推进到商机阶段",
        },
        {
            "input": {"customer_id": "uuid-xxxx", "new_stage": "customer"},
            "output_summary": "将客户标记为成交，触发成交事件",
        },
    ]
    gotchas = "会自动创建一条deal_update类型的跟进记录。成交时触发DEAL_WON事件，进入商机阶段触发LEAD_QUALIFIED事件。不校验阶段跳转合理性（如可直接从线索跳到成交）。"
    related_tools = ["get_customer_detail", "update_customer", "get_sales_pipeline"]
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
    domain = "crm"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        customer_id = args.get("customer_id", "")
        new_stage = args.get("new_stage", "")

        if not customer_id or not new_stage:
            return self.format_result(data=None, summary="客户ID和新阶段不能为空")
        if err := _validate_uuid(customer_id, "customer_id"):
            return self.format_result(data=None, summary=err)

        if new_stage not in CUSTOMER_STAGES:
            return self.format_result(data=None, summary=f"无效的阶段: {new_stage}，可选: {', '.join(CUSTOMER_STAGES)}")

        old_customer = await crm_service.get_customer(customer_id, db=client)
        if not old_customer:
            return self.format_result(data=None, summary=f"未找到ID为 {customer_id} 的客户")

        old_stage = old_customer.get("stage", "unknown")

        try:
            customer = await crm_service.update_customer(
                customer_id, {"stage": new_stage}, db=client
            )
        except Exception as e:
            return safe_tool_error(e, "阶段变更")

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
            logger.error(f"Event emission failed: {e}")

        stage_labels = {
            "lead": "线索",
            "prospect": "意向",
            "opportunity": "商机",
            "customer": "成交",
            "churned": "流失",
        }

        return self.format_result(
            data={"customer": customer, "old_stage": old_stage, "new_stage": new_stage},
            summary=f"客户 {customer.get('name', '')} 阶段已更新: {stage_labels.get(old_stage, old_stage)} → {stage_labels.get(new_stage, new_stage)}",
            actions=[
                {"label": "查看详情", "tool": "get_customer_detail", "args": {"customer_id": customer_id}},
                {"label": "查看销售漏斗", "tool": "get_sales_pipeline", "args": {}},
            ],
        )


class GetSalesPipelineTool(BaseTool):
    """获取销售漏斗视图"""

    name = "get_sales_pipeline"
    description = "获取销售漏斗视图，展示各阶段客户数量和预估金额分布"
    examples = [
        {
            "input": {},
            "output_summary": "返回销售漏斗概览，包括客户总数、本月新增、转化率和各阶段分布表",
        },
    ]
    gotchas = "会额外查询全部客户来计算各阶段金额，客户数量较多时可能较慢。无参数，直接调用即可。"
    related_tools = ["get_customers", "update_customer_stage"]

    parameters = {"type": "object", "properties": {}, "required": []}
    domain = "crm"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return self.format_result(data=None, summary="无法获取组织信息，请确保已正确登录")

        stats = await crm_service.get_customer_stats(org_id, db=client)
        if not stats or stats.get("total_customers", 0) == 0:
            return self.format_result(
                data=None,
                summary="当前暂无客户数据",
                actions=[{"label": "创建客户", "tool": "create_customer", "args": {}}],
            )

        # stage_distribution is a list of {stage, name, count, color} — convert to dict
        stage_dist_list = stats.get("stage_distribution", [])
        stage_dist = (
            {item["stage"]: item["count"] for item in stage_dist_list}
            if isinstance(stage_dist_list, list)
            else stage_dist_list
        )

        # 获取各阶段金额
        all_customers = await crm_service.list_customers(org_id, db=client)
        stage_values = {}
        for c in all_customers or []:
            s = c.get("stage", "lead")
            v = float(c.get("estimated_value") or 0)
            stage_values[s] = stage_values.get(s, 0) + v

        pipeline_data = {
            "total_customers": stats.get("total_customers", 0),
            "new_this_month": stats.get("new_this_month", 0),
            "conversion_rate": stats.get("conversion_rate", 0),
            "total_estimated_value": float(stats.get("total_estimated_value", 0)),
            "stages": {
                stage_key: {"count": stage_dist.get(stage_key, 0), "value": stage_values.get(stage_key, 0)}
                for stage_key in ("lead", "prospect", "opportunity", "customer", "churned")
            },
        }

        return self.format_result(
            data=pipeline_data,
            summary=f"销售漏斗: {stats.get('total_customers', 0)} 位客户, 总金额 ¥{float(stats.get('total_estimated_value', 0)):,.0f}",
            actions=[
                {"label": "查看客户列表", "tool": "get_customers", "args": {}},
                {"label": "推进阶段", "tool": "update_customer_stage", "args": {}},
            ],
        )


@register_tool(
    name="get_pipeline_kanban", category="crm", description="获取看板视图的销售漏斗"
)
class GetPipelineKanbanTool(BaseTool):
    """获取销售漏斗看板视图"""

    name = "get_pipeline_kanban"
    description = "获取销售漏斗看板数据，包含每个阶段的客户列表和总金额，用于呈现 Kanban 视图或者了解各个阶段的具体客户组成"
    examples = [
        {"input": {}, "output_summary": "返回按阶段分组（看板）的详细列表及其总额"},
    ]
    gotchas = "不包含已流失的详细客户。返回较为结构化或列表呈现的数据。"
    related_tools = ["get_customers", "get_sales_pipeline"]

    parameters = {"type": "object", "properties": {}, "required": []}
    domain = "crm"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return self.format_result(data=None, summary="无法获取组织信息，请确保已正确登录")

        kanban_list = await crm_service.get_pipeline_kanban(org_id, db=client)
        if not kanban_list:
            return self.format_result(
                data=None,
                summary="当前暂无客户数据",
                actions=[{"label": "创建客户", "tool": "create_customer", "args": {}}],
            )

        # Filter out churned for kanban view
        kanban_data = [stage for stage in kanban_list if stage.get("id") != "churned"]

        return self.format_result(
            data=kanban_data,
            summary=f"销售漏斗看板: {len(kanban_data)} 个阶段",
            actions=[
                {"label": "查看客户列表", "tool": "get_customers", "args": {}},
                {"label": "查看销售漏斗", "tool": "get_sales_pipeline", "args": {}},
            ],
        )
