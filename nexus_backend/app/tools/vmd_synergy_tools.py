"""
VMD 产研销协同工具集 (Virtual Marketing Department - Synergy Tools)

工作项 #31: 为市场-研发-销售协同提供数据支撑
- 行业动态监测
- 市场调研报告
- 竞品全维度分析
- 客户反馈汇总
"""

import logging
from typing import Any

from app.services.ai_service import AIService
from app.services.vector_service import vector_service
from app.tools.web_search_helper import search_web

from .base_tool import BaseTool
from ._shared import _get_client

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  行业动态监测工具
# ═══════════════════════════════════════════════════════════════════════════════


class MonitorIndustryTrendsTool(BaseTool):
    """监测科学仪器行业动态"""

    name = "monitor_industry_trends"
    description = "监测科学仪器行业动态、政策变化和技术趋势，生成分析报告。当用户说'行业动态'、'最新趋势'、'政策变化'、'市场动态'时调用。"
    required_role = "all"
    examples = [
        {"input": {"category": "policy", "industry": "环保监测"}, "output_summary": "生成环保监测领域最新政策法规动态报告"},
        {"input": {"category": "technology", "keywords": "拉曼光谱,AI检测"}, "output_summary": "生成拉曼光谱和AI检测相关的技术趋势报告"},
        {"input": {}, "output_summary": "生成科学仪器行业全面动态报告"},
    ]
    related_tools = ["generate_market_research", "generate_competitor_analysis"]
    gotchas = "所有参数均为可选。category可选值: policy/technology/market/competitor/all。会联网搜索最新信息，每条信息标注来源。"

    parameters = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["policy", "technology", "market", "competitor", "all"],
                "description": "关注类别: policy=政策法规, technology=技术趋势, market=市场动态, competitor=竞品动向, all=全部",
            },
            "industry": {
                "type": "string",
                "description": "细分行业（如：环保监测、制药分析、食品安全）",
            },
            "keywords": {
                "type": "string",
                "description": "关注的关键词（逗号分隔）",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        category = args.get("category", "all")
        industry = args.get("industry", "科学仪器")
        keywords = args.get("keywords", "")

        category_labels = {
            "policy": "政策法规",
            "technology": "技术趋势",
            "market": "市场动态",
            "competitor": "竞品动向",
            "all": "全面行业动态",
        }

        # Search knowledge base for industry intelligence
        kb_context = ""
        try:
            org_id = config.get("org_id") if config else None
            search_query = f"{industry} {category_labels.get(category, '')} {keywords} 动态 趋势".strip()
            kb_result = await vector_service.search(
                search_query,
                user_id,
                limit=5,
                config=config,
                org_id=org_id,
            )
            if kb_result and "No relevant documents" not in kb_result:
                kb_context = f"\n\n## 知识库已有情报\n{kb_result}"
        except Exception as e:
            logger.warning(f"Knowledge base search failed for industry trends: {e}")

        # 联网搜索最新行业动态
        web_context = ""
        try:
            web_query = f"{industry} {category_labels.get(category, '行业')} {keywords} 最新动态 2024 2025".strip()
            web_result = await search_web(web_query, count=5, freshness="pm")
            if web_result:
                web_context = f"\n\n## 互联网最新情报（实时搜索）\n{web_result}"
        except Exception as e:
            logger.warning(f"Web search failed for industry trends: {e}")

        prompt = (
            f"请生成一份{category_labels.get(category, '全面')}行业动态分析报告：\n\n"
            f"- 行业：{industry}\n"
            f"- 关注类别：{category_labels.get(category, '全面')}\n"
            f"- 关键词：{keywords or '无特定关键词'}\n"
            f"{kb_context}\n{web_context}\n\n"
            f"请涵盖以下方面：\n"
            f"1. **政策法规** — 最新行业政策、标准更新\n"
            f"2. **技术发展** — 新技术、新方法进展\n"
            f"3. **市场趋势** — 市场规模、增长预测、采购趋势\n"
            f"4. **竞品动向** — 主要竞品的新品、策略变化\n"
            f"5. **机会识别** — 值得关注的商业机会\n"
            f"6. **风险提示** — 需要警惕的行业风险\n"
            f"7. **行动建议** — 对我方的具体建议\n\n"
            f"请综合知识库资料和互联网搜索结果进行分析。标注每条信息的来源（知识库/网络搜索/行业通识）。"
        )

        system = (
            "你是科学仪器行业分析师，擅长行业情报监测和趋势研判。"
            "请综合内部知识库和互联网搜索结果提供有价值的行业洞察。"
            "标注信息来源（知识库/网络搜索/行业通识），给出可操作的建议。中文输出。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            return f"📡 **行业动态报告 — {industry}**\n\n{result}"
        except Exception as e:
            logger.error(f"Failed to monitor industry trends: {e}")
            return f"❌ 生成行业动态报告失败: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════════
#  市场调研报告工具
# ═══════════════════════════════════════════════════════════════════════════════


class GenerateMarketResearchTool(BaseTool):
    """生成市场需求调研报告"""

    name = "generate_market_research"
    description = "生成目标市场的需求调研报告，分析市场规模、客户需求和竞争格局。当用户说'市场调研'、'市场分析'、'需求调研'时调用。"
    required_role = "all"
    examples = [
        {"input": {"market_segment": "环保监测仪器市场", "region": "华东"}, "output_summary": "生成华东地区环保监测仪器市场调研报告"},
        {"input": {"market_segment": "制药分析仪器", "research_focus": "客户需求,市场规模"}, "output_summary": "生成聚焦需求和规模的制药分析仪器调研报告"},
    ]
    related_tools = ["monitor_industry_trends", "generate_competitor_analysis"]
    gotchas = "market_segment为必填。会综合知识库、CRM客户数据和联网搜索三个数据源，部分来源可能为空但不影响报告生成。"

    parameters = {
        "type": "object",
        "properties": {
            "market_segment": {
                "type": "string",
                "description": "目标市场细分（如：环保监测仪器市场）",
            },
            "research_focus": {
                "type": "string",
                "description": "调研重点（如：客户需求、市场规模、渠道分析）",
            },
            "region": {
                "type": "string",
                "description": "目标区域（如：华东、全国、东南亚）",
            },
        },
        "required": ["market_segment"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        market_segment = args.get("market_segment", "").strip()
        if not market_segment:
            return "❌ 请提供目标市场细分。"

        research_focus = args.get("research_focus", "")
        region = args.get("region", "国内")

        # Search knowledge base
        kb_context = ""
        try:
            org_id = config.get("org_id") if config else None
            search_query = f"{market_segment} 市场 需求 规模 {region}".strip()
            kb_result = await vector_service.search(
                search_query,
                user_id,
                limit=5,
                config=config,
                org_id=org_id,
            )
            if kb_result and "No relevant documents" not in kb_result:
                kb_context = f"\n\n## 知识库市场资料\n{kb_result}"
        except Exception as e:
            logger.warning(f"Knowledge base search failed for market research: {e}")

        # Gather internal data
        internal_data = ""
        try:
            client = _get_client(config)
            if client:
                # Get customer distribution by industry
                customers_res = await client.table("customers").select("industry, stage").execute()
                if customers_res.data:
                    industry_dist = {}
                    for c in customers_res.data:
                        ind = c.get("industry", "未分类") or "未分类"
                        industry_dist[ind] = industry_dist.get(ind, 0) + 1
                    internal_data += f"\n## 内部客户行业分布\n{industry_dist}\n"
        except Exception as e:
            logger.warning(f"Failed to gather internal data: {e}")

        # 联网搜索市场数据
        web_context = ""
        try:
            web_query = f"{market_segment} 市场规模 增长率 趋势 {region}".strip()
            web_result = await search_web(web_query, count=5, freshness="py")
            if web_result:
                web_context = f"\n\n## 互联网市场数据（实时搜索）\n{web_result}"
        except Exception as e:
            logger.warning(f"Web search failed for market research: {e}")

        prompt = (
            f"请生成市场需求调研报告：\n\n"
            f"- 目标市场：{market_segment}\n"
            f"- 调研重点：{research_focus or '全面调研'}\n"
            f"- 目标区域：{region}\n"
            f"{kb_context}\n{internal_data}\n{web_context}\n\n"
            f"报告结构：\n"
            f"1. **市场概述** — 市场定义、规模估算、增长趋势\n"
            f"2. **需求分析** — 客户核心需求、痛点、采购偏好\n"
            f"3. **竞争格局** — 主要参与者、市场份额、竞争策略\n"
            f"4. **渠道分析** — 销售渠道构成、渠道效率\n"
            f"5. **价格分析** — 价格带分布、定价策略\n"
            f"6. **机会与风险** — SWOT分析\n"
            f"7. **进入策略** — 建议的市场进入/拓展策略\n"
            f"8. **预测** — 未来3年市场预测\n"
        )

        system = (
            "你是科学仪器行业的市场研究专家。"
            "请综合知识库资料、内部数据和互联网搜索结果生成结构化的调研报告。"
            "标注数据来源（知识库/内部数据/网络搜索/合理估算）。中文输出。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            return f"📊 **市场调研报告 — {market_segment}**\n\n{result}"
        except Exception as e:
            logger.error(f"Failed to generate market research: {e}")
            return f"❌ 生成市场调研报告失败: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════════
#  竞品全维度分析工具
# ═══════════════════════════════════════════════════════════════════════════════


class GenerateCompetitorAnalysisTool(BaseTool):
    """生成竞品全维度分析报告"""

    name = "generate_competitor_analysis"
    description = "生成竞品公司的全维度分析报告，涵盖产品、技术、市场和组织等维度。当用户说'竞品分析'、'研究对手'、'竞争对手报告'时调用。"
    required_role = "all"
    examples = [
        {"input": {"competitor_name": "安捷伦", "analysis_depth": "deep", "focus_product": "气相色谱"}, "output_summary": "生成安捷伦气相色谱产品线的深度分析报告"},
        {"input": {"competitor_name": "赛默飞", "analysis_depth": "quick"}, "output_summary": "生成赛默飞的快速概览分析"},
    ]
    related_tools = ["generate_competitor_comparison", "monitor_industry_trends", "generate_market_research"]
    gotchas = "analysis_depth可选值: quick/standard/deep，不传默认standard。与generate_competitor_comparison的区别：本工具分析整个公司，后者对比具体产品参数。"

    parameters = {
        "type": "object",
        "properties": {
            "competitor_name": {
                "type": "string",
                "description": "竞品公司/品牌名称",
            },
            "analysis_depth": {
                "type": "string",
                "enum": ["quick", "standard", "deep"],
                "description": "分析深度: quick=快速概览, standard=标准分析, deep=深度研究",
            },
            "focus_product": {
                "type": "string",
                "description": "重点对标的产品线（可选）",
            },
        },
        "required": ["competitor_name"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        competitor_name = args.get("competitor_name", "").strip()
        if not competitor_name:
            return "❌ 请提供竞品公司/品牌名称。"

        analysis_depth = args.get("analysis_depth", "standard")
        focus_product = args.get("focus_product", "")

        depth_labels = {"quick": "快速概览", "standard": "标准分析", "deep": "深度研究"}

        # Search knowledge base
        kb_context = ""
        try:
            org_id = config.get("org_id") if config else None
            search_query = f"{competitor_name} {focus_product} 竞品 分析 产品线 市场策略".strip()
            kb_result = await vector_service.search(
                search_query,
                user_id,
                limit=5,
                config=config,
                org_id=org_id,
            )
            if kb_result and "No relevant documents" not in kb_result:
                kb_context = f"\n\n## 知识库竞品资料\n{kb_result}"
        except Exception as e:
            logger.warning(f"Knowledge base search failed for competitor analysis: {e}")

        # 联网搜索竞品最新动态
        web_context = ""
        try:
            web_query = f"{competitor_name} {focus_product} 新品 策略 营收 动态".strip()
            web_result = await search_web(web_query, count=5, freshness="py")
            if web_result:
                web_context = f"\n\n## 互联网竞品情报（实时搜索）\n{web_result}"
        except Exception as e:
            logger.warning(f"Web search failed for competitor analysis: {e}")

        prompt = (
            f"请生成{depth_labels.get(analysis_depth, '标准')}竞品分析报告：\n\n"
            f"- 竞品：{competitor_name}\n"
            f"- 分析深度：{depth_labels.get(analysis_depth, '标准')}\n"
            f"- 重点产品：{focus_product or '全产品线'}\n"
            f"{kb_context}\n{web_context}\n\n"
            f"分析维度：\n"
            f"1. **公司概况** — 规模、营收、发展历程\n"
            f"2. **产品矩阵** — 主要产品线、明星产品、新品动态\n"
            f"3. **技术实力** — 专利、研发投入、技术路线\n"
            f"4. **市场策略** — 定价策略、渠道布局、营销手段\n"
            f"5. **客户分析** — 主要客群、标杆客户、客户评价\n"
            f"6. **优劣势评估** — SWOT分析\n"
            f"7. **对标建议** — 我方应对策略和差异化方向\n"
        )

        system = (
            "你是科学仪器行业的竞争情报分析师。"
            "请综合知识库资料和互联网搜索结果提供客观、深入的竞品分析。"
            "标注数据来源（知识库/网络搜索/行业估算）。中文输出。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            return f"🔎 **竞品分析 — {competitor_name}**\n\n{result}"
        except Exception as e:
            logger.error(f"Failed to generate competitor analysis: {e}")
            return f"❌ 生成竞品分析失败: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════════
#  客户反馈汇总工具
# ═══════════════════════════════════════════════════════════════════════════════


class AggregateCustomerFeedbackTool(BaseTool):
    """汇总分析客户反馈和售后痛点"""

    name = "aggregate_customer_feedback"
    description = "汇总分析客户反馈和售后痛点，为产品改进和研发提供依据。当用户说'客户反馈'、'售后问题汇总'、'用户痛点'、'VOC分析'时调用。"
    required_role = "all"
    examples = [
        {"input": {"product_name": "ICP-MS 7800", "time_range": "last_quarter", "feedback_type": "complaint"}, "output_summary": "汇总近一季度ICP-MS相关投诉，分析高频问题和痛点"},
        {"input": {"time_range": "last_year", "feedback_type": "all"}, "output_summary": "生成近一年全部产品的客户反馈汇总分析"},
    ]
    related_tools = ["customer_lifecycle_analysis", "generate_faq_response", "generate_repurchase_campaign"]
    gotchas = "所有参数均为可选。time_range可选值: last_month/last_quarter/last_year/all。feedback_type可选值: complaint/suggestion/praise/all。CRM活动数据最多取100条。"

    parameters = {
        "type": "object",
        "properties": {
            "product_name": {
                "type": "string",
                "description": "产品名称（可选，不填则分析全部产品）",
            },
            "time_range": {
                "type": "string",
                "enum": ["last_month", "last_quarter", "last_year", "all"],
                "description": "时间范围: last_month=近一个月, last_quarter=近一季度, last_year=近一年, all=全部",
            },
            "feedback_type": {
                "type": "string",
                "enum": ["complaint", "suggestion", "praise", "all"],
                "description": "反馈类型: complaint=投诉, suggestion=建议, praise=好评, all=全部",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        product_name = args.get("product_name", "")
        time_range = args.get("time_range", "last_quarter")
        feedback_type = args.get("feedback_type", "all")

        # Validate enum values to prevent invalid_text_representation errors
        if time_range not in ("last_month", "last_quarter", "last_year", "all"):
            return f"不支持的时间范围: {time_range}，请使用 last_month/last_quarter/last_year/all。"
        if feedback_type not in ("complaint", "suggestion", "praise", "all"):
            return f"不支持的反馈类型: {feedback_type}，请使用 complaint/suggestion/praise/all。"

        time_labels = {
            "last_month": "近一个月",
            "last_quarter": "近一季度",
            "last_year": "近一年",
            "all": "全部时间",
        }

        # Gather CRM activity data (follow-up notes containing feedback)
        feedback_data = []
        try:
            client = _get_client(config)
            if client:
                query = client.table("customer_activities").select("*").order("created_at", desc=True).limit(100)
                if feedback_type != "all":
                    query = query.ilike("content", f"%{feedback_type}%")
                activities_res = await query.execute()

                if activities_res.data:
                    for act in activities_res.data:
                        feedback_data.append(f"- [{act.get('activity_type', '')}] {act.get('content', '')[:150]}")
        except Exception as e:
            logger.warning(f"Failed to gather feedback data from CRM: {e}")

        # Search knowledge base for feedback patterns
        kb_context = ""
        try:
            org_id = config.get("org_id") if config else None
            search_query = f"{product_name} 客户反馈 问题 投诉 建议".strip()
            kb_result = await vector_service.search(
                search_query,
                user_id,
                limit=5,
                config=config,
                org_id=org_id,
            )
            if kb_result and "No relevant documents" not in kb_result:
                kb_context = f"\n\n## 知识库客户反馈记录\n{kb_result}"
        except Exception as e:
            logger.warning(f"Knowledge base search failed for feedback: {e}")

        feedback_text = "\n".join(feedback_data[:50]) if feedback_data else "暂无CRM反馈数据"

        prompt = (
            f"请汇总分析客户反馈：\n\n"
            f"- 产品：{product_name or '全部产品'}\n"
            f"- 时间范围：{time_labels.get(time_range, '近一季度')}\n"
            f"- 反馈类型：{feedback_type}\n\n"
            f"## CRM跟进记录中的反馈\n{feedback_text}\n"
            f"{kb_context}\n\n"
            f"请生成：\n"
            f"1. **反馈概览** — 反馈总量、分类统计\n"
            f"2. **高频问题TOP5** — 最常见的客户问题\n"
            f"3. **痛点分析** — 客户核心痛点和根因分析\n"
            f"4. **产品改进建议** — 基于反馈的产品优化方向\n"
            f"5. **服务改进建议** — 售后服务流程改善建议\n"
            f"6. **正面反馈亮点** — 客户满意的方面\n"
            f"7. **给研发的建议** — 需要研发关注的技术问题\n"
            f"8. **给销售的提示** — 销售需要注意的客户关切\n"
        )

        system = (
            "你是客户体验和VOC（Voice of Customer）分析专家。"
            "请从客户反馈中提炼有价值的洞察，为产研销协同提供依据。"
            "分析要具体、可操作。中文输出。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            return f"📢 **客户反馈汇总分析**\n\n{result}"
        except Exception as e:
            logger.error(f"Failed to aggregate customer feedback: {e}")
            return f"❌ 汇总客户反馈失败: {str(e)}"
