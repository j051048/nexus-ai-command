"""
VMD 运营工具集 (Virtual Marketing Department - Operation Tools)

工作项: 为设备运营和客户生命周期管理提供智能支持
- 设备维护保养提醒
- 产品FAQ智能回复
- 老客户复购营销方案
- 客户生命周期分析
"""

import logging
from typing import Any

from app.core.database import supabase
from app.services.ai_service import AIService
from app.services.vector_service import vector_service

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


def _get_client(config: dict = None):
    """Get scoped DB client if user token available, else fallback to service client."""
    token = config.get("token") if config else None
    return supabase.get_scoped_client(token) if token and supabase else supabase


# ═══════════════════════════════════════════════════════════════════════════════
#  设备维护保养提醒工具
# ═══════════════════════════════════════════════════════════════════════════════


class GenerateMaintenanceReminderTool(BaseTool):
    """生成设备维护保养提醒和服务通知"""

    name = "generate_maintenance_reminder"
    description = "生成设备维护保养提醒和服务通知。" "当用户说'维护提醒'、'保养通知'、'售后提醒'时调用。"
    required_role = "all"

    parameters = {
        "type": "object",
        "properties": {
            "product_name": {
                "type": "string",
                "description": "产品/设备名称",
            },
            "maintenance_type": {
                "type": "string",
                "enum": ["routine", "calibration", "repair", "upgrade"],
                "description": "维护类型: routine=常规保养, calibration=校准维护, repair=维修服务, upgrade=升级服务",
            },
            "customer_name": {
                "type": "string",
                "description": "客户名称（可选，指定后生成个性化提醒）",
            },
        },
        "required": ["product_name", "maintenance_type"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        product_name = args.get("product_name", "").strip()
        if not product_name:
            return "❌ 请提供产品/设备名称。"

        maintenance_type = args.get("maintenance_type", "routine")
        customer_name = args.get("customer_name", "")

        type_labels = {
            "routine": "常规保养",
            "calibration": "校准维护",
            "repair": "维修服务",
            "upgrade": "升级服务",
        }

        # Search knowledge base for product maintenance info
        kb_context = ""
        try:
            org_id = config.get("org_id") if config else None
            search_query = f"{product_name} 维护 保养 {type_labels.get(maintenance_type, '')} 操作规程 注意事项".strip()
            kb_result = await vector_service.search(
                search_query,
                user_id,
                limit=5,
                config=config,
                org_id=org_id,
            )
            if kb_result and "No relevant documents" not in kb_result:
                kb_context = f"\n\n## 知识库产品维护资料\n{kb_result}"
        except Exception as e:
            logger.warning(f"Knowledge base search failed for maintenance reminder: {e}")

        customer_note = f"- 客户名称：{customer_name}\n" if customer_name else ""

        prompt = (
            f"请生成一份专业的设备维护保养提醒通知：\n\n"
            f"- 产品/设备：{product_name}\n"
            f"- 维护类型：{type_labels.get(maintenance_type, '常规保养')}\n"
            f"{customer_note}"
            f"{kb_context}\n\n"
            f"请涵盖以下内容：\n"
            f"1. **维护提醒标题** — 简洁明了的提醒主题\n"
            f"2. **维护计划** — 建议的维护时间安排和周期\n"
            f"3. **维护步骤** — 具体的维护操作步骤和要点\n"
            f"4. **注意事项** — 维护过程中需要特别注意的事项\n"
            f"5. **所需耗材/配件** — 维护可能需要的耗材或配件清单\n"
            f"6. **联系方式** — 售后服务联系方式和预约提示\n"
            f"7. **温馨提示** — 延期维护可能带来的风险提醒\n\n"
            f"请基于知识库产品资料生成准确的维护内容，语气专业且友好。"
        )

        system = (
            "你是科学仪器售后服务专家，擅长设备维护保养规划和客户服务通知撰写。"
            "请基于知识库资料生成专业、准确的维护提醒通知。"
            "内容要具体可操作，语气专业且温暖。中文输出。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            target = f" — {customer_name}" if customer_name else ""
            return f"🔧 **设备维护提醒{target} — {product_name}**\n\n{result}"
        except Exception as e:
            logger.error(f"Failed to generate maintenance reminder: {e}")
            return f"❌ 生成维护保养提醒失败: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════════
#  产品FAQ智能回复工具
# ═══════════════════════════════════════════════════════════════════════════════


class GenerateFaqResponseTool(BaseTool):
    """智能回答产品常见问题，基于知识库生成精准FAQ回复"""

    name = "generate_faq_response"
    description = (
        "智能回答产品常见问题，基于知识库生成精准FAQ回复。" "当用户说'FAQ'、'常见问题'、'产品问题回复'时调用。"
    )
    required_role = "all"

    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "客户提出的问题",
            },
            "product_name": {
                "type": "string",
                "description": "相关产品名称（可选，帮助缩小检索范围）",
            },
            "response_style": {
                "type": "string",
                "enum": ["formal", "friendly", "technical"],
                "description": "回复风格: formal=正式专业, friendly=友好亲切, technical=技术详尽",
            },
        },
        "required": ["question"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        question = args.get("question", "").strip()
        if not question:
            return "❌ 请提供客户的问题内容。"

        product_name = args.get("product_name", "")
        response_style = args.get("response_style", "friendly")

        style_labels = {
            "formal": "正式专业",
            "friendly": "友好亲切",
            "technical": "技术详尽",
        }

        style_instructions = {
            "formal": "语气正式、专业，使用标准术语，适合书面沟通。",
            "friendly": "语气友好、亲切，通俗易懂，适合日常客户沟通。",
            "technical": "侧重技术细节，提供深入的技术解释和参数说明，适合技术人员。",
        }

        # Search knowledge base for relevant answers
        kb_context = ""
        try:
            org_id = config.get("org_id") if config else None
            search_query = f"{product_name} {question}".strip()
            kb_result = await vector_service.search(
                search_query,
                user_id,
                limit=5,
                config=config,
                org_id=org_id,
            )
            if kb_result and "No relevant documents" not in kb_result:
                kb_context = f"\n\n## 知识库相关资料\n{kb_result}"
        except Exception as e:
            logger.warning(f"Knowledge base search failed for FAQ response: {e}")

        product_note = f"- 相关产品：{product_name}\n" if product_name else ""

        prompt = (
            f"请基于知识库资料回答以下客户问题：\n\n"
            f"- 客户问题：{question}\n"
            f"{product_note}"
            f"- 回复风格：{style_labels.get(response_style, '友好亲切')}\n"
            f"{kb_context}\n\n"
            f"请生成回复，包含：\n"
            f"1. **直接回答** — 简洁明了地回答核心问题\n"
            f"2. **详细说明** — 展开解释，提供必要的背景信息\n"
            f"3. **操作建议** — 如果适用，提供具体的操作步骤\n"
            f"4. **参考资料** — 引用知识库中的相关文档或资料\n"
            f"5. **延伸建议** — 相关的补充信息或常见关联问题\n\n"
            f"如果知识库中没有直接匹配的信息，请基于行业通识回答并标注。"
        )

        system = (
            f"你是科学仪器产品专家和客户服务专家。"
            f"请基于知识库资料精准回答客户问题。"
            f"{style_instructions.get(response_style, style_instructions['friendly'])}"
            f"确保回答准确、有参考价值。标注信息来源（知识库/行业通识）。中文输出。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            return f"💡 **FAQ智能回复**\n\n**问题：** {question}\n\n{result}"
        except Exception as e:
            logger.error(f"Failed to generate FAQ response: {e}")
            return f"❌ 生成FAQ回复失败: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════════
#  老客户复购营销方案工具
# ═══════════════════════════════════════════════════════════════════════════════


class GenerateRepurchaseCampaignTool(BaseTool):
    """生成老客户复购/增购营销方案"""

    name = "generate_repurchase_campaign"
    description = "生成老客户复购/增购营销方案。" "当用户说'复购方案'、'老客户营销'、'增购计划'时调用。"
    required_role = "all"

    parameters = {
        "type": "object",
        "properties": {
            "customer_segment": {
                "type": "string",
                "description": "目标客户群体（如：高校实验室、环保监测站、制药企业）",
            },
            "product_category": {
                "type": "string",
                "description": "产品类别（可选，如：光谱仪、色谱仪）",
            },
            "campaign_type": {
                "type": "string",
                "enum": ["repurchase", "upgrade", "cross_sell", "referral"],
                "description": "营销类型: repurchase=复购, upgrade=升级换代, cross_sell=交叉销售, referral=转介绍",
            },
        },
        "required": ["customer_segment", "campaign_type"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        customer_segment = args.get("customer_segment", "").strip()
        if not customer_segment:
            return "❌ 请提供目标客户群体。"

        product_category = args.get("product_category", "")
        campaign_type = args.get("campaign_type", "repurchase")

        type_labels = {
            "repurchase": "复购营销",
            "upgrade": "升级换代",
            "cross_sell": "交叉销售",
            "referral": "转介绍推荐",
        }

        # Query CRM data for customer segment insights
        crm_context = ""
        try:
            client = _get_client(config)
            if client:
                # Get customers matching the segment
                customers_res = (
                    await client.table("customers").select("name, industry, stage, source, created_at").execute()
                )

                if customers_res.data:
                    total_customers = len(customers_res.data)
                    stage_dist = {}
                    industry_dist = {}
                    for c in customers_res.data:
                        stage = c.get("stage", "未分类") or "未分类"
                        stage_dist[stage] = stage_dist.get(stage, 0) + 1
                        ind = c.get("industry", "未分类") or "未分类"
                        industry_dist[ind] = industry_dist.get(ind, 0) + 1

                    crm_context += (
                        f"\n## CRM客户数据概览\n"
                        f"- 总客户数：{total_customers}\n"
                        f"- 阶段分布：{stage_dist}\n"
                        f"- 行业分布：{industry_dist}\n"
                    )
        except Exception as e:
            logger.warning(f"Failed to gather CRM data for repurchase campaign: {e}")

        # Search knowledge base for product and marketing materials
        kb_context = ""
        try:
            org_id = config.get("org_id") if config else None
            search_query = f"{customer_segment} {product_category} 复购 营销 优惠 方案".strip()
            kb_result = await vector_service.search(
                search_query,
                user_id,
                limit=5,
                config=config,
                org_id=org_id,
            )
            if kb_result and "No relevant documents" not in kb_result:
                kb_context = f"\n\n## 知识库营销资料\n{kb_result}"
        except Exception as e:
            logger.warning(f"Knowledge base search failed for repurchase campaign: {e}")

        product_note = f"- 产品类别：{product_category}\n" if product_category else ""

        prompt = (
            f"请生成一份{type_labels.get(campaign_type, '复购')}营销方案：\n\n"
            f"- 目标客群：{customer_segment}\n"
            f"{product_note}"
            f"- 营销类型：{type_labels.get(campaign_type, '复购营销')}\n"
            f"{crm_context}\n{kb_context}\n\n"
            f"方案结构：\n"
            f"1. **目标定义** — 营销目标、预期转化率、ROI预估\n"
            f"2. **客户筛选** — 目标客户画像、筛选条件、预估覆盖人数\n"
            f"3. **价值主张** — 核心卖点、客户利益点\n"
            f"4. **营销话术** — 不同触点的沟通话术（邮件/电话/微信）\n"
            f"5. **优惠策略** — 折扣方案、赠品方案、限时活动\n"
            f"6. **触达计划** — 多渠道触达时间线和节奏\n"
            f"7. **跟进流程** — 销售跟进的SOP和话术\n"
            f"8. **效果评估** — KPI指标和效果追踪方法\n"
        )

        system = (
            "你是科学仪器行业的营销策划专家，擅长B2B客户复购和增购策略。"
            "请基于CRM数据和知识库资料生成可落地执行的营销方案。"
            "方案要具体、有数据支撑、可操作。中文输出。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            return f"🎯 **{type_labels.get(campaign_type, '复购')}营销方案 — {customer_segment}**\n\n{result}"
        except Exception as e:
            logger.error(f"Failed to generate repurchase campaign: {e}")
            return f"❌ 生成复购营销方案失败: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════════
#  客户生命周期分析工具
# ═══════════════════════════════════════════════════════════════════════════════


class CustomerLifecycleAnalysisTool(BaseTool):
    """分析客户生命周期价值和健康度"""

    name = "customer_lifecycle_analysis"
    description = "分析客户生命周期价值和健康度。" "当用户说'客户分析'、'生命周期'、'客户健康度'、'LTV分析'时调用。"
    required_role = "all"

    parameters = {
        "type": "object",
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "客户ID（可选，不填则分析全部客户）",
            },
            "time_range": {
                "type": "string",
                "enum": ["last_quarter", "last_year", "all"],
                "description": "分析时间范围: last_quarter=近一季度, last_year=近一年, all=全部",
            },
            "analysis_focus": {
                "type": "string",
                "enum": ["health", "ltv", "churn_risk", "engagement"],
                "description": "分析重点: health=健康度评估, ltv=生命周期价值, churn_risk=流失风险, engagement=互动活跃度",
            },
        },
        "required": ["time_range", "analysis_focus"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        customer_id = args.get("customer_id", "")
        time_range = args.get("time_range", "last_year")
        analysis_focus = args.get("analysis_focus", "health")

        time_labels = {
            "last_quarter": "近一季度",
            "last_year": "近一年",
            "all": "全部时间",
        }

        focus_labels = {
            "health": "健康度评估",
            "ltv": "生命周期价值(LTV)",
            "churn_risk": "流失风险预警",
            "engagement": "互动活跃度",
        }

        # Query CRM customers data
        customers_data = ""
        activities_data = ""
        try:
            client = _get_client(config)
            if client:
                # Get customer info
                if customer_id:
                    customers_res = await client.table("customers").select("*").eq("id", customer_id).execute()
                else:
                    customers_res = (
                        await client.table("customers")
                        .select("id, name, industry, stage, source, created_at")
                        .limit(200)
                        .execute()
                    )

                if customers_res.data:
                    total = len(customers_res.data)
                    stage_dist = {}
                    industry_dist = {}
                    source_dist = {}
                    for c in customers_res.data:
                        stage = c.get("stage", "未分类") or "未分类"
                        stage_dist[stage] = stage_dist.get(stage, 0) + 1
                        ind = c.get("industry", "未分类") or "未分类"
                        industry_dist[ind] = industry_dist.get(ind, 0) + 1
                        src = c.get("source", "未知") or "未知"
                        source_dist[src] = source_dist.get(src, 0) + 1

                    customers_data = (
                        f"\n## CRM客户数据\n"
                        f"- 分析客户数：{total}\n"
                        f"- 阶段分布：{stage_dist}\n"
                        f"- 行业分布：{industry_dist}\n"
                        f"- 来源分布：{source_dist}\n"
                    )

                    if customer_id and customers_res.data:
                        cust = customers_res.data[0]
                        customers_data += (
                            f"- 客户详情：{cust.get('name', '')} | "
                            f"行业：{cust.get('industry', '未知')} | "
                            f"阶段：{cust.get('stage', '未知')} | "
                            f"创建时间：{cust.get('created_at', '未知')}\n"
                        )

                # Get customer activities
                activity_query = (
                    client.table("customer_activities")
                    .select("customer_id, activity_type, content, created_at")
                    .order("created_at", desc=True)
                    .limit(200)
                )

                if customer_id:
                    activity_query = activity_query.eq("customer_id", customer_id)

                activities_res = await activity_query.execute()

                if activities_res.data:
                    activity_count = len(activities_res.data)
                    type_dist = {}
                    for act in activities_res.data:
                        atype = act.get("activity_type", "未分类") or "未分类"
                        type_dist[atype] = type_dist.get(atype, 0) + 1

                    recent_activities = []
                    for act in activities_res.data[:20]:
                        recent_activities.append(
                            f"  - [{act.get('activity_type', '')}] "
                            f"{act.get('content', '')[:100]} "
                            f"({act.get('created_at', '')[:10]})"
                        )

                    activities_data = (
                        f"\n## 客户活动数据\n"
                        f"- 活动总数：{activity_count}\n"
                        f"- 类型分布：{type_dist}\n"
                        f"- 近期活动记录：\n" + "\n".join(recent_activities) + "\n"
                    )
        except Exception as e:
            logger.warning(f"Failed to gather CRM data for lifecycle analysis: {e}")

        # Search knowledge base for customer management best practices
        kb_context = ""
        try:
            org_id = config.get("org_id") if config else None
            search_query = f"客户生命周期 {focus_labels.get(analysis_focus, '')} LTV 流失 分析".strip()
            kb_result = await vector_service.search(
                search_query,
                user_id,
                limit=5,
                config=config,
                org_id=org_id,
            )
            if kb_result and "No relevant documents" not in kb_result:
                kb_context = f"\n\n## 知识库参考资料\n{kb_result}"
        except Exception as e:
            logger.warning(f"Knowledge base search failed for lifecycle analysis: {e}")

        customer_note = f"- 指定客户ID：{customer_id}\n" if customer_id else "- 范围：全部客户\n"

        prompt = (
            f"请生成客户生命周期分析报告：\n\n"
            f"{customer_note}"
            f"- 时间范围：{time_labels.get(time_range, '近一年')}\n"
            f"- 分析重点：{focus_labels.get(analysis_focus, '健康度评估')}\n"
            f"{customers_data}\n{activities_data}\n{kb_context}\n\n"
            f"请涵盖以下分析维度：\n"
            f"1. **客户概览** — 客户群体画像和基本统计\n"
            f"2. **健康度评分** — 基于互动频率、阶段进展、活动数据的健康评分\n"
            f"3. **LTV估算** — 客户生命周期价值估算和分层\n"
            f"4. **流失风险识别** — 高风险客户特征和预警信号\n"
            f"5. **互动分析** — 客户互动频率、渠道偏好、响应率\n"
            f"6. **生命周期阶段** — 各阶段客户分布和转化漏斗\n"
            f"7. **关键洞察** — 数据驱动的核心发现\n"
            f"8. **行动建议** — 针对不同客户群的具体行动计划\n"
        )

        system = (
            "你是B2B客户成功和客户分析专家，擅长客户生命周期管理和数据分析。"
            "请基于CRM数据和知识库资料生成深入的客户分析报告。"
            "分析要有数据支撑，建议要具体可执行。中文输出。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            scope = f"客户 {customer_id}" if customer_id else "全部客户"
            return f"📈 **客户生命周期分析 — {scope}**\n\n{result}"
        except Exception as e:
            logger.error(f"Failed to generate customer lifecycle analysis: {e}")
            return f"❌ 生成客户生命周期分析失败: {str(e)}"
