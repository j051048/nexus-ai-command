"""
VMD 销售赋能工具集 (Virtual Marketing Department - Sales Enablement Tools)

工作项 #30: 为销售团队提供话术、竞品分析、培训和报价支持
- 销售话术生成
- 竞品对比分析
- 培训材料生成
- 报价单模板生成
"""

import logging
from typing import Any

from app.services.ai_service import AIService
from app.services.vector_service import vector_service
from app.tools._shared import safe_tool_error
from app.tools.web_search_helper import search_web

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  销售话术生成工具
# ═══════════════════════════════════════════════════════════════════════════════


class GenerateSalesScriptTool(BaseTool):
    """生成科学仪器产品销售话术"""

    name = "generate_sales_script"
    domain = "vmd_content"
    description = "生成指定产品的销售话术和技术答疑口径。当用户说'销售话术'、'怎么和客户说'、'产品卖点'、'FAQs回答'时调用。"
    required_role = "all"
    examples = [
        {"input": {"product_name": "ICP-MS 7800", "scenario": "cold_call", "customer_type": "高校实验室"}, "output_summary": "生成ICP-MS 7800针对高校实验室的陌生拜访话术"},
        {"input": {"product_name": "气相色谱仪", "scenario": "objection_handling", "competitor": "安捷伦8890"}, "output_summary": "生成气相色谱仪面对安捷伦竞品时的异议处理话术"},
    ]
    related_tools = ["generate_competitor_comparison", "generate_training_material", "generate_quotation_template"]
    gotchas = "scenario可选值: cold_call/demo/objection_handling/closing/follow_up，不传默认cold_call。competitor为可选参数，填写后会自动检索竞品情报。"

    parameters = {
        "type": "object",
        "properties": {
            "product_name": {
                "type": "string",
                "description": "产品名称",
            },
            "scenario": {
                "type": "string",
                "enum": ["cold_call", "demo", "objection_handling", "closing", "follow_up"],
                "description": "场景: cold_call=陌生拜访, demo=产品演示, objection_handling=异议处理, closing=促成成交, follow_up=跟进维护",
            },
            "customer_type": {
                "type": "string",
                "description": "客户类型（如：高校实验室、药企QC、环保监测站）",
            },
            "competitor": {
                "type": "string",
                "description": "客户正在考虑的竞品（可选）",
            },
        },
        "required": ["product_name"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        product_name = args.get("product_name", "").strip()
        if not product_name:
            return "❌ 请提供产品名称。"

        scenario = args.get("scenario", "cold_call")
        customer_type = args.get("customer_type", "")
        competitor = args.get("competitor", "")

        scenario_labels = {
            "cold_call": "陌生拜访",
            "demo": "产品演示",
            "objection_handling": "异议处理",
            "closing": "促成成交",
            "follow_up": "跟进维护",
        }

        # Search knowledge base for product info and competitive intelligence
        kb_context = ""
        try:
            org_id = config.get("org_id") if config else None
            search_query = f"{product_name} 卖点 优势 {competitor}".strip()
            kb_result = await vector_service.search(
                search_query,
                user_id,
                limit=5,
                config=config,
                org_id=org_id,
            )
            if kb_result and "No relevant documents" not in kb_result:
                kb_context = f"\n\n## 产品知识库资料\n{kb_result}"
        except Exception as e:
            logger.warning(f"Knowledge base search failed for sales script: {e}")

        prompt = (
            f"请为以下场景生成销售话术：\n\n"
            f"- 产品：{product_name}\n"
            f"- 场景：{scenario_labels.get(scenario, '陌生拜访')}\n"
            f"- 客户类型：{customer_type or '通用'}\n"
            f"- 竞品：{competitor or '无'}\n"
            f"{kb_context}\n\n"
            f"请生成以下内容：\n"
            f"1. **开场白** — 如何切入话题，引起客户兴趣\n"
            f"2. **核心卖点** — 3-5个需要强调的关键优势\n"
            f"3. **常见问题应答** — 客户可能问到的5个问题及标准回答\n"
            f"4. **异议处理** — 价格太贵/不需要/再考虑等常见异议的话术\n"
            f"5. **促成话术** — 如何推动客户做出决定\n"
            f"6. **禁忌提醒** — 不能说的话和敏感话题\n\n"
            f"话术要自然、专业，不要太像背稿。"
        )

        system = (
            "你是科学仪器行业的金牌销售培训师。"
            "生成的话术要实战导向，结合行业特点，帮助销售人员快速上手。"
            "包含技术细节但避免过于复杂。中文输出。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            return f"🎯 **销售话术 — {product_name}（{scenario_labels.get(scenario, '')}）**\n\n{result}"
        except Exception as e:
            logger.error(f"Failed to generate sales script: {e}")
            return safe_tool_error(e, "生成销售话术")


# ═══════════════════════════════════════════════════════════════════════════════
#  竞品对比分析工具
# ═══════════════════════════════════════════════════════════════════════════════


class GenerateCompetitorComparisonTool(BaseTool):
    """生成竞品对比分析表"""

    name = "generate_competitor_comparison"
    domain = "vmd_content"
    description = "生成我方产品与竞品的对比分析表，含技术参数、价格和优劣势。当用户说'竞品对比'、'和XX比怎么样'、'竞品分析表'时调用。"
    required_role = "all"
    examples = [
        {"input": {"our_product": "GC-2030", "competitors": "安捷伦8890,岛津GCMS-QP2020"}, "output_summary": "生成GC-2030与两款竞品的全面对比分析表"},
        {"input": {"our_product": "UV-2600", "competitors": "PE Lambda 365", "comparison_focus": "灵敏度,性价比"}, "output_summary": "生成聚焦灵敏度和性价比的紫外分光光度计对比"},
    ]
    related_tools = ["generate_sales_script", "generate_competitor_analysis"]
    gotchas = "competitors支持逗号分隔多个竞品。会同时检索知识库和联网搜索，联网搜索可能因网络问题失败但不影响整体结果。"

    parameters = {
        "type": "object",
        "properties": {
            "our_product": {
                "type": "string",
                "description": "我方产品名称",
            },
            "competitors": {
                "type": "string",
                "description": "竞品名称（多个用逗号分隔，如：安捷伦8890,岛津GCMS-QP2020）",
            },
            "comparison_focus": {
                "type": "string",
                "description": "对比重点（如：灵敏度、性价比、售后服务）",
            },
        },
        "required": ["our_product", "competitors"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        our_product = args.get("our_product", "").strip()
        competitors = args.get("competitors", "").strip()
        if not our_product or not competitors:
            return "❌ 请提供我方产品名称和竞品名称。"

        comparison_focus = args.get("comparison_focus", "")

        # Search knowledge base
        kb_context = ""
        try:
            org_id = config.get("org_id") if config else None
            search_query = f"{our_product} {competitors} 参数 对比 优势"
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
            logger.warning(f"Knowledge base search failed for competitor comparison: {e}")

        # 联网搜索竞品最新参数和评价
        web_context = ""
        try:
            web_query = f"{our_product} {competitors} 参数对比 评测 {comparison_focus}".strip()
            web_result = await search_web(web_query, count=5)
            if web_result:
                web_context = f"\n\n## 互联网竞品数据（实时搜索）\n{web_result}"
        except Exception as e:
            logger.warning(f"Web search failed for competitor comparison: {e}")

        prompt = (
            f"请生成竞品对比分析表：\n\n"
            f"- 我方产品：{our_product}\n"
            f"- 竞品：{competitors}\n"
            f"- 对比重点：{comparison_focus or '全面对比'}\n"
            f"{kb_context}\n{web_context}\n\n"
            f"请按以下结构输出：\n"
            f"1. **对比总览表** — Markdown表格，维度包含：核心性能、价格区间、售后服务、易用性、口碑\n"
            f"2. **我方优势** — 我方产品相对竞品的差异化优势\n"
            f"3. **我方劣势** — 需要注意和规避的短板\n"
            f"4. **应对策略** — 面对每个竞品时的销售策略建议\n"
            f"5. **客户话术** — 当客户提到竞品时的标准应对话术\n\n"
            f"数据要基于知识库资料，未找到的数据请标注'需确认'。"
        )

        system = (
            "你是科学仪器行业的市场竞争分析专家。"
            "请客观分析各产品的优劣势，同时为销售团队提供可操作的竞争策略。"
            "数据需要注明来源（知识库/行业估算），不要编造参数。中文输出。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            return f"⚔️ **竞品对比分析 — {our_product} vs {competitors}**\n\n{result}"
        except Exception as e:
            logger.error(f"Failed to generate competitor comparison: {e}")
            return safe_tool_error(e, "生成竞品对比分析")


# ═══════════════════════════════════════════════════════════════════════════════
#  培训材料生成工具
# ═══════════════════════════════════════════════════════════════════════════════


class GenerateTrainingMaterialTool(BaseTool):
    """生成销售培训课件大纲和内容"""

    name = "generate_training_material"
    domain = "vmd_content"
    description = "生成销售培训课件大纲和核心内容。当用户说'培训课件'、'新人培训'、'产品培训'时调用。"
    required_role = "all"
    examples = [
        {"input": {"topic": "新产品ICP-MS培训", "audience": "new_hire", "duration": "2小时"}, "output_summary": "生成面向新人的ICP-MS产品培训课件大纲"},
        {"input": {"topic": "高端客户谈判技巧", "audience": "experienced"}, "output_summary": "生成面向资深销售的谈判技巧培训材料"},
    ]
    related_tools = ["generate_sales_script", "generate_competitor_comparison"]
    gotchas = "audience可选值: new_hire/experienced/manager/technical，不传默认new_hire。duration为自由文本，如'30分钟'、'半天'。"

    parameters = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "培训主题（如：新产品培训、销售技巧、竞品分析）",
            },
            "audience": {
                "type": "string",
                "enum": ["new_hire", "experienced", "manager", "technical"],
                "description": "受众: new_hire=新人, experienced=老销售, manager=管理层, technical=技术支持",
            },
            "duration": {
                "type": "string",
                "description": "培训时长（如：30分钟、1小时、半天）",
            },
            "product_name": {
                "type": "string",
                "description": "涉及的产品（可选）",
            },
        },
        "required": ["topic"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        topic = args.get("topic", "").strip()
        if not topic:
            return "❌ 请提供培训主题。"

        audience = args.get("audience", "new_hire")
        duration = args.get("duration", "1小时")
        product_name = args.get("product_name", "")

        audience_labels = {
            "new_hire": "新入职销售",
            "experienced": "资深销售",
            "manager": "销售管理层",
            "technical": "技术支持人员",
        }

        # Search knowledge base
        kb_context = ""
        try:
            org_id = config.get("org_id") if config else None
            search_query = f"{topic} {product_name} 培训 知识点".strip()
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
            logger.warning(f"Knowledge base search failed for training material: {e}")

        prompt = (
            f"请生成销售培训课件大纲和核心内容：\n\n"
            f"- 培训主题：{topic}\n"
            f"- 目标受众：{audience_labels.get(audience, '新入职销售')}\n"
            f"- 培训时长：{duration}\n"
            f"- 涉及产品：{product_name or '通用'}\n"
            f"{kb_context}\n\n"
            f"请提供：\n"
            f"1. **培训目标** — 学员完成培训后应掌握的能力\n"
            f"2. **课件大纲** — 分章节的详细大纲（含时间分配）\n"
            f"3. **核心知识点** — 每章节的关键知识点\n"
            f"4. **案例/情境** — 可用于课堂讨论的案例\n"
            f"5. **互动环节** — 角色扮演、测验等互动设计\n"
            f"6. **课后作业** — 巩固学习的练习任务\n"
            f"7. **评估方式** — 如何考核培训效果\n"
        )

        system = (
            "你是科学仪器行业的销售培训专家。"
            "请设计实战导向的培训课件，注重互动和案例教学。"
            "内容要符合目标受众的认知水平。中文输出。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            return f"📚 **培训课件 — {topic}**\n\n{result}"
        except Exception as e:
            logger.error(f"Failed to generate training material: {e}")
            return safe_tool_error(e, "生成培训材料")


# ═══════════════════════════════════════════════════════════════════════════════
#  报价单模板生成工具
# ═══════════════════════════════════════════════════════════════════════════════


class GenerateQuotationTemplateTool(BaseTool):
    """生成产品报价单模板"""

    name = "generate_quotation_template"
    domain = "vmd_content"
    description = "生成产品报价单模板，含产品配置、价格明细和优惠方案。当用户说'报价单'、'做报价'、'价格方案'时调用。"
    required_role = "all"
    examples = [
        {"input": {"products": "XX光谱仪标配+自动进样器", "customer_name": "中科院化学所", "include_service": True}, "output_summary": "生成含售后服务的光谱仪报价单模板"},
        {"input": {"products": "气相色谱仪GC-2030, 液相色谱仪LC-20A", "discount_policy": "年底促销9折"}, "output_summary": "生成两台仪器的促销报价单模板"},
    ]
    related_tools = ["generate_sales_script", "generate_competitor_comparison"]
    gotchas = "价格处会标注'[需填入]'，不会编造实际价格。include_service默认为true。products为必填，customer_name可后续填写。"

    parameters = {
        "type": "object",
        "properties": {
            "customer_name": {
                "type": "string",
                "description": "客户名称",
            },
            "products": {
                "type": "string",
                "description": "产品列表及配置（如：XX光谱仪标配+自动进样器）",
            },
            "include_service": {
                "type": "boolean",
                "description": "是否包含售后服务报价",
            },
            "discount_policy": {
                "type": "string",
                "description": "优惠政策说明（可选）",
            },
        },
        "required": ["products"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        products = args.get("products", "").strip()
        if not products:
            return "❌ 请提供产品列表。"

        customer_name = args.get("customer_name", "")
        include_service = args.get("include_service", True)
        discount_policy = args.get("discount_policy", "")

        # Search knowledge base for product pricing
        kb_context = ""
        try:
            org_id = config.get("org_id") if config else None
            kb_result = await vector_service.search(
                f"{products} 价格 配置 报价",
                user_id,
                limit=5,
                config=config,
                org_id=org_id,
            )
            if kb_result and "No relevant documents" not in kb_result:
                kb_context = f"\n\n## 产品价格参考\n{kb_result}"
        except Exception as e:
            logger.warning(f"Knowledge base search failed for quotation: {e}")

        service_note = "（包含售后服务报价）" if include_service else "（不含售后服务）"

        prompt = (
            f"请生成一份产品报价单模板{service_note}：\n\n"
            f"- 客户：{customer_name or '____（待填写）'}\n"
            f"- 产品配置：{products}\n"
            f"- 优惠政策：{discount_policy or '标准价格'}\n"
            f"{kb_context}\n\n"
            f"报价单格式：\n"
            f"1. **报价单头** — 编号、日期、有效期、客户信息\n"
            f"2. **产品明细表** — 序号、品名、型号、数量、单价、小计\n"
            f"3. **配件清单** — 随机配件和可选配件\n"
        )

        if include_service:
            prompt += (
                "4. **服务项目** — 安装调试、培训、质保延长等\n"
                "5. **付款条件** — 付款方式、进度款\n"
                "6. **交付说明** — 交货周期、运输方式\n"
                "7. **质保条款** — 质保期限、服务响应\n"
            )
        else:
            prompt += "4. **付款条件** — 付款方式\n5. **交付说明** — 交货周期、运输方式\n"

        prompt += "\n请用 Markdown 表格展示价格明细，价格处标注'[需填入]'。"

        system = (
            "你是科学仪器行业的商务专家。"
            "请生成规范的报价单模板，格式专业，信息完整。"
            "价格信息需要标注为待填写，不要编造价格。中文输出。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            return f"💰 **报价单模板**\n\n{result}"
        except Exception as e:
            logger.error(f"Failed to generate quotation template: {e}")
            return safe_tool_error(e, "生成报价单")
