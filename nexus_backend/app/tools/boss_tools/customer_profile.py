"""AI 客户画像自动生成"""

import logging
from typing import Any

from app.services.ai_service import AIService
from app.tools._shared import safe_tool_error

from ..base_tool import BaseTool
from ..boss_shared import _get_client

logger = logging.getLogger(__name__)


class CustomerProfileTool(BaseTool):
    """AI 客户画像自动生成"""

    name = "generate_customer_profile"
    description = "根据客户关系管理数据生成客户画像分析，包含标签、偏好和跟进建议。当用户说'分析客户'、'客户画像'时调用。"
    required_role = "all"
    domain = "crm"
    examples = [
        {
            "input": {"customer_name": "华为"},
            "output_summary": "返回华为的AI客户画像（标签、偏好、风险、跟进策略）",
        },
        {
            "input": {"customer_name": "张总"},
            "output_summary": "返回与张总相关的客户画像分析",
        },
    ]
    related_tools = ["search_customers", "get_customer_detail"]
    gotchas = "按客户名称或公司名称模糊匹配，结果取前10条。会调用大模型生成画像，响应可能稍慢。"

    parameters = {
        "type": "object",
        "properties": {
            "customer_name": {
                "type": "string",
                "description": "客户/公司名称",
            }
        },
        "required": ["customer_name"],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        from app.services.crm_service import crm_service

        name = args.get("customer_name", "")
        if not name:
            return "❌ 请提供客户名称（customer_name）"
        client = _get_client(config)
        org_id = config.get("org_id") if config else None

        # Search customers table (new CRM system)
        try:
            customers = []
            if org_id:
                customers = await crm_service.search_customers(org_id, name, db=client)
            if not customers:
                # Fallback: try direct query by company or name
                res = (
                    await client.table("customers")
                    .select("*")
                    .or_(f"name.ilike.%{name}%,company.ilike.%{name}%")
                    .limit(10)
                    .execute()
                )
                customers = res.data or []
        except Exception as e:
            return safe_tool_error(e, "查询客户数据")

        if not customers:
            return f"未找到与 '{name}' 相关的客户记录。请确认客户名称是否正确。"

        # Build summary from customers table
        stage_labels = {
            "lead": "线索",
            "prospect": "意向",
            "opportunity": "商机",
            "customer": "成交",
            "churned": "流失",
        }
        leads_summary = []
        customer_id = customers[0]["id"]
        for c in customers:
            stage = stage_labels.get(c.get("stage", ""), c.get("stage", ""))
            value = c.get("estimated_value") or 0
            leads_summary.append(
                f"- 客户: {c.get('name', '未知')}, 公司: {c.get('company', '未知')}, "
                f"行业: {c.get('industry', '未知')}, 阶段: {stage}, "
                f"预估金额: ¥{float(value):,.0f}, 来源: {c.get('source', '未知')}, "
                f"最后更新: {str(c.get('updated_at', ''))[:10]}"
            )

        # Fetch contacts and recent activities for richer profile
        try:
            contacts = await crm_service.list_contacts(customer_id, db=client)
            if contacts:
                leads_summary.append("\n联系人:")
                for ct in contacts:
                    primary = " (主要联系人)" if ct.get("is_primary") else ""
                    leads_summary.append(
                        f"  - {ct.get('name', '未知')}{primary}, "
                        f"职位: {ct.get('title', '未知')}, "
                        f"电话: {ct.get('phone', '')}, 邮箱: {ct.get('email', '')}"
                    )

            activities = await crm_service.get_activity_timeline(
                customer_id, limit=5, db=client
            )
            if activities:
                type_labels = {
                    "call": "电话",
                    "email": "邮件",
                    "meeting": "会议",
                    "note": "备注",
                    "deal_update": "商机更新",
                }
                leads_summary.append("\n最近跟进:")
                for act in activities:
                    t = type_labels.get(
                        act.get("activity_type", ""), act.get("activity_type", "")
                    )
                    leads_summary.append(
                        f"  - [{t}] {act.get('content', '')[:80]} ({str(act.get('created_at', ''))[:10]})"
                    )
        except Exception as e:
            logger.debug("客户跟进记录查询失败: %s", e)

        prompt = (
            "客户数据:\n"
            + "\n".join(leads_summary)
            + "\n\n请生成客户画像，包括：客户标签、合作偏好、风险评估、推荐跟进策略。"
        )
        system = (
            "你是资深CRM分析师，基于客户交互历史生成精准画像。用中文回复，格式清晰。"
        )

        try:
            profile = await AIService.call_llm(prompt, system)
            return f"👤 {name} 客户画像:\n\n{profile}"
        except Exception as e:
            return safe_tool_error(e, "客户画像生成")
