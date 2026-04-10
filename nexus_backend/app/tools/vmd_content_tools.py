"""
VMD 内容营销工具集 (Virtual Marketing Department - Content Tools)

工作项 #27-28: 为 content_agent 提供科学仪器行业内容生成能力
- 产品手册生成
- 技术白皮书生成
- 应用方案文档生成
- 自媒体文案生成
"""

import logging
from typing import Any

from app.services.ai_service import AIService
from app.services.vector_service import vector_service
from app.tools._shared import safe_tool_error

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  产品手册生成工具
# ═══════════════════════════════════════════════════════════════════════════════


class GenerateProductManualTool(BaseTool):
    """基于知识库生成科学仪器产品手册框架"""

    name = "generate_product_manual"
    domain = "vmd_content"
    description = "基于知识库生成科学仪器产品手册框架，含产品概述、技术参数、应用场景和操作指南等章节。当用户说'生成产品手册'、'编写产品资料'、'产品文档'时调用。"
    required_role = "all"
    examples = [
        {
            "input": {
                "product_name": "ICP-MS 7800",
                "product_category": "质谱仪器",
                "target_audience": "实验室技术人员",
            },
            "output_summary": "生成ICP-MS面向实验室技术人员的产品手册框架",
        },
        {
            "input": {
                "product_name": "UV-2600",
                "key_features": "双光束设计,超低杂散光",
            },
            "output_summary": "生成突出关键特性的UV-2600产品手册框架",
        },
    ]
    related_tools = [
        "generate_whitepaper",
        "generate_application_note",
        "generate_social_post",
    ]
    gotchas = "product_name为必填。知识库无相关资料时会基于行业通用规范生成框架并标注需补充的部分。各字段有最大长度限制。"

    parameters = {
        "type": "object",
        "properties": {
            "product_name": {
                "type": "string",
                "maxLength": 200,
                "description": "产品名称",
            },
            "product_category": {
                "type": "string",
                "maxLength": 200,
                "description": "产品类别（如：光谱仪器、色谱仪器、质谱仪器等）",
            },
            "target_audience": {
                "type": "string",
                "maxLength": 200,
                "description": "目标读者（如：实验室技术人员、采购决策者）",
            },
            "key_features": {
                "type": "string",
                "maxLength": 2000,
                "description": "需要突出的关键特性",
            },
        },
        "required": ["product_name"],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        product_name = args.get("product_name", "").strip()
        if not product_name:
            return "❌ 请提供产品名称。"

        product_category = args.get("product_category", "科学仪器")
        target_audience = args.get("target_audience", "实验室技术人员和采购决策者")
        key_features = args.get("key_features", "")

        # 1. Search knowledge base for product information
        kb_context = ""
        try:
            org_id = config.get("org_id") if config else None
            kb_result = await vector_service.search(
                f"{product_name} 产品技术参数 规格 特性",
                user_id,
                limit=5,
                config=config,
                org_id=org_id,
            )
            if kb_result and "No relevant documents" not in kb_result:
                kb_context = f"\n\n## 知识库参考资料\n{kb_result}"
        except Exception as e:
            logger.warning(f"Knowledge base search failed for product manual: {e}")

        # 2. Build prompt with context
        prompt = (
            f"请为以下科学仪器产品生成一份专业的产品手册框架：\n\n"
            f"- 产品名称：{product_name}\n"
            f"- 产品类别：{product_category}\n"
            f"- 目标读者：{target_audience}\n"
            f"- 关键特性：{key_features or '请根据知识库资料提炼'}\n"
            f"{kb_context}\n\n"
            f"请按以下章节结构生成手册框架，每个章节提供详细的内容要点：\n"
            f"1. **产品概述** — 产品定位、核心价值主张\n"
            f"2. **技术参数** — 关键性能指标、规格表\n"
            f"3. **产品优势** — 与竞品对比的差异化优势\n"
            f"4. **应用场景** — 典型行业应用和用例\n"
            f"5. **操作指南** — 快速上手步骤、注意事项\n"
            f"6. **维护保养** — 日常维护、校准要求\n"
            f"7. **配件与耗材** — 推荐配件清单\n"
            f"8. **售后服务** — 质保政策、技术支持\n\n"
            f"请确保内容专业、准确，符合科学仪器行业规范。"
        )

        system = (
            "你是科学仪器行业的技术文档专家，擅长撰写专业的产品手册和技术文档。"
            "请基于提供的知识库资料生成内容，如果知识库中没有相关信息，请基于行业通用规范生成框架并标注需要补充的部分。"
            "使用中文输出，格式清晰，适合直接用于产品宣传。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            return f"📘 **{product_name} 产品手册框架**\n\n{result}"
        except Exception as e:
            logger.error(f"Failed to generate product manual: {e}")
            return safe_tool_error(e, "生成产品手册")


# ═══════════════════════════════════════════════════════════════════════════════
#  技术白皮书生成工具
# ═══════════════════════════════════════════════════════════════════════════════


class GenerateWhitepaperTool(BaseTool):
    """生成科学仪器行业技术白皮书"""

    name = "generate_whitepaper"
    domain = "vmd_content"
    description = "生成科学仪器行业技术白皮书，含行业背景、技术原理、解决方案和应用案例。当用户说'写白皮书'、'技术白皮书'、'行业白皮书'时调用。"
    required_role = "all"
    examples = [
        {
            "input": {
                "topic": "新一代拉曼光谱在制药行业的应用",
                "industry": "制药",
                "technology": "拉曼光谱",
                "depth": "detailed",
            },
            "output_summary": "生成详细级的拉曼光谱制药应用白皮书框架",
        },
        {
            "input": {"topic": "环境水质在线监测技术发展趋势", "depth": "overview"},
            "output_summary": "生成概述级的水质监测技术白皮书",
        },
    ]
    related_tools = [
        "generate_product_manual",
        "generate_application_note",
        "generate_social_post",
    ]
    gotchas = "topic为必填。depth可选值: overview/detailed/expert，不传默认detailed。生成的是框架和要点，需要补充实际数据的位置会标注。"

    parameters = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "白皮书主题（如：新一代拉曼光谱在制药行业的应用）",
            },
            "industry": {
                "type": "string",
                "description": "目标行业（如：制药、环保、食品安全、材料科学）",
            },
            "technology": {
                "type": "string",
                "description": "核心技术/产品（如：拉曼光谱、气相色谱、ICP-MS）",
            },
            "depth": {
                "type": "string",
                "enum": ["overview", "detailed", "expert"],
                "description": "深度级别: overview=概述, detailed=详细, expert=专家级",
            },
        },
        "required": ["topic"],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        topic = args.get("topic", "").strip()
        if not topic:
            return "❌ 请提供白皮书主题。"

        industry = args.get("industry", "")
        technology = args.get("technology", "")
        depth = args.get("depth", "detailed")

        depth_labels = {"overview": "概述级", "detailed": "详细级", "expert": "专家级"}

        # Search knowledge base
        kb_context = ""
        try:
            org_id = config.get("org_id") if config else None
            search_query = f"{topic} {technology} {industry} 技术原理 应用案例".strip()
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
            logger.warning(f"Knowledge base search failed for whitepaper: {e}")

        prompt = (
            f"请生成一份{depth_labels.get(depth, '详细级')}技术白皮书框架：\n\n"
            f"- 主题：{topic}\n"
            f"- 目标行业：{industry or '通用'}\n"
            f"- 核心技术：{technology or '待确定'}\n"
            f"{kb_context}\n\n"
            f"白皮书结构：\n"
            f"1. **摘要** — 核心观点和价值主张（200字以内）\n"
            f"2. **行业背景** — 行业痛点、市场趋势、法规要求\n"
            f"3. **技术原理** — 核心技术解析、工作原理\n"
            f"4. **解决方案** — 我方方案优势、技术架构\n"
            f"5. **应用案例** — 2-3个典型客户案例（可虚构框架）\n"
            f"6. **数据对比** — 性能数据、ROI分析\n"
            f"7. **实施建议** — 部署路径、选型指南\n"
            f"8. **未来展望** — 技术发展趋势\n"
            f"9. **参考文献** — 建议引用的标准和文献\n\n"
            f"请确保内容专业严谨，数据有理有据。"
        )

        system = (
            "你是科学仪器行业的技术营销专家，擅长撰写行业白皮书和技术报告。"
            "请生成的白皮书要兼具技术深度和商业价值，适合向行业客户传播。"
            "基于知识库资料编写，标注需要补充实际数据的位置。中文输出。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            return f"📄 **技术白皮书 — {topic}**\n\n{result}"
        except Exception as e:
            logger.error(f"Failed to generate whitepaper: {e}")
            return safe_tool_error(e, "生成白皮书")


# ═══════════════════════════════════════════════════════════════════════════════
#  应用方案文档生成工具
# ═══════════════════════════════════════════════════════════════════════════════


class GenerateApplicationNoteTool(BaseTool):
    """生成科学仪器应用方案文档"""

    name = "generate_application_note"
    domain = "vmd_content"
    description = "生成针对特定行业或场景的科学仪器应用方案文档。当用户说'写应用方案'、'应用笔记'、'解决方案文档'时调用。"
    required_role = "all"
    examples = [
        {
            "input": {
                "application": "土壤重金属检测",
                "instrument": "ICP-MS 7800",
                "sample_type": "土壤",
                "standard": "GB/T 17141",
            },
            "output_summary": "生成土壤重金属ICP-MS检测的完整应用方案",
        },
        {
            "input": {"application": "药品溶出度测试", "instrument": "紫外分光光度计"},
            "output_summary": "生成药品溶出度测试的应用方案文档",
        },
    ]
    related_tools = ["generate_product_manual", "generate_whitepaper"]
    gotchas = "application为必填，其余参数可选填'待确定'由模型根据知识库补充。文档涵盖从样品前处理到数据分析的完整实验流程。"

    parameters = {
        "type": "object",
        "properties": {
            "application": {
                "type": "string",
                "description": "应用场景（如：土壤重金属检测、药品质量控制）",
            },
            "instrument": {
                "type": "string",
                "description": "使用的仪器型号或类别",
            },
            "sample_type": {
                "type": "string",
                "description": "样品类型（如：水样、土壤、生物组织）",
            },
            "standard": {
                "type": "string",
                "description": "相关标准或法规（如：GB/T、EPA方法）",
            },
        },
        "required": ["application"],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        application = args.get("application", "").strip()
        if not application:
            return "❌ 请描述应用场景。"

        instrument = args.get("instrument", "")
        sample_type = args.get("sample_type", "")
        standard = args.get("standard", "")

        # Search knowledge base
        kb_context = ""
        try:
            org_id = config.get("org_id") if config else None
            search_query = f"{application} {instrument} {sample_type} 方法 参数".strip()
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
            logger.warning(f"Knowledge base search failed for application note: {e}")

        prompt = (
            f"请生成一份应用方案文档：\n\n"
            f"- 应用场景：{application}\n"
            f"- 仪器：{instrument or '待确定'}\n"
            f"- 样品类型：{sample_type or '待确定'}\n"
            f"- 相关标准：{standard or '待确定'}\n"
            f"{kb_context}\n\n"
            f"文档结构：\n"
            f"1. **应用概述** — 应用背景、检测需求\n"
            f"2. **仪器配置** — 推荐仪器及配件清单\n"
            f"3. **样品前处理** — 取样、制样步骤\n"
            f"4. **分析方法** — 仪器参数设置、测量步骤\n"
            f"5. **数据分析** — 数据处理方法、结果解读\n"
            f"6. **方法验证** — 检出限、精密度、准确度\n"
            f"7. **典型结果** — 示例数据和图表描述\n"
            f"8. **注意事项** — 常见问题和解决办法\n"
        )

        system = "你是科学仪器应用工程师，擅长编写应用方案和方法学文档。内容需要专业准确，涵盖完整的实验流程。中文输出。"

        try:
            result = await AIService.call_llm(prompt, system)
            return f"🔬 **应用方案 — {application}**\n\n{result}"
        except Exception as e:
            logger.error(f"Failed to generate application note: {e}")
            return safe_tool_error(e, "生成应用方案")


# ═══════════════════════════════════════════════════════════════════════════════
#  自媒体文案生成工具
# ═══════════════════════════════════════════════════════════════════════════════


class GenerateSocialPostTool(BaseTool):
    """生成科学仪器行业自媒体文案"""

    name = "generate_social_post"
    domain = "vmd_content"
    description = "生成适配各平台的科学仪器行业自媒体文案。当用户说'写公众号文案'、'生成社媒内容'、'发朋友圈'、'写推文'时调用。"
    required_role = "all"
    examples = [
        {
            "input": {
                "topic": "新品发布会预告",
                "platform": "wechat",
                "tone": "promotional",
                "product_name": "ICP-MS 7800",
            },
            "output_summary": "生成微信公众号风格的新品发布推广长文",
        },
        {
            "input": {
                "topic": "实验室安全知识科普",
                "platform": "weibo",
                "tone": "casual",
            },
            "output_summary": "生成微博风格的140字以内实验室安全科普短文",
        },
    ]
    related_tools = [
        "generate_product_manual",
        "generate_whitepaper",
        "generate_application_note",
    ]
    gotchas = "platform可选值: wechat/linkedin/forum/weibo/general，不同平台字数和风格差异很大。tone可选值: professional/casual/academic/promotional。"

    parameters = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "文案主题（如：新品发布、技术科普、展会预告）",
            },
            "platform": {
                "type": "string",
                "enum": ["wechat", "linkedin", "forum", "weibo", "general"],
                "description": "目标平台: wechat=微信公众号, linkedin=LinkedIn, forum=行业论坛, weibo=微博, general=通用",
            },
            "tone": {
                "type": "string",
                "enum": ["professional", "casual", "academic", "promotional"],
                "description": "语调风格: professional=专业, casual=轻松, academic=学术, promotional=推广",
            },
            "product_name": {
                "type": "string",
                "description": "涉及的产品名称（可选）",
            },
        },
        "required": ["topic"],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        topic = args.get("topic", "").strip()
        if not topic:
            return "❌ 请提供文案主题。"

        platform = args.get("platform", "general")
        tone = args.get("tone", "professional")
        product_name = args.get("product_name", "")

        platform_labels = {
            "wechat": "微信公众号（1500-3000字长文，配图文排版建议）",
            "linkedin": "LinkedIn（300-600字专业短文，英文标签建议）",
            "forum": "行业论坛（800-1500字技术分享帖）",
            "weibo": "微博（140字以内短文+话题标签）",
            "general": "通用文案（800-1500字）",
        }

        tone_labels = {
            "professional": "专业严谨",
            "casual": "轻松易懂",
            "academic": "学术化",
            "promotional": "推广导向",
        }

        # Search knowledge base for relevant context — always attempt
        # When product_name is specified, search with it; otherwise use topic alone
        kb_context = ""
        try:
            org_id = config.get("org_id") if config else None
            search_query = f"{product_name} {topic}" if product_name else topic
            kb_result = await vector_service.search(
                search_query,
                user_id,
                limit=3,
                config=config,
                org_id=org_id,
            )
            if (
                kb_result
                and "No relevant documents" not in kb_result
                and "未找到" not in kb_result
            ):
                kb_context = f"\n\n## 参考资料（来自知识库）\n{kb_result}"
        except Exception as e:
            logger.warning(f"Knowledge base search failed for social post: {e}")

        prompt = (
            f"请生成一篇科学仪器行业自媒体文案：\n\n"
            f"- 主题：{topic}\n"
            f"- 目标平台：{platform_labels.get(platform, '通用')}\n"
            f"- 语调风格：{tone_labels.get(tone, '专业')}\n"
            f"- 涉及产品：{product_name or '无特定产品'}\n"
            f"{kb_context}\n\n"
            f"要求：\n"
            f"1. 标题吸引眼球，适合目标平台传播\n"
            f"2. 内容专业但不晦涩，有行业洞察\n"
            f"3. 适当融入产品信息，避免硬广\n"
            f"4. 包含互动引导（提问、投票等）\n"
            f"5. 建议配图方向和关键词标签\n"
        )

        system = (
            "你是科学仪器行业的自媒体运营专家，擅长在不同平台创作高质量技术内容。"
            "文案要兼顾专业性和可读性，符合目标平台的传播特点。中文输出。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            platform_name = {
                "wechat": "微信公众号",
                "linkedin": "LinkedIn",
                "forum": "行业论坛",
                "weibo": "微博",
                "general": "通用",
            }.get(platform, "通用")
            return f"📱 **{platform_name}文案 — {topic}**\n\n{result}"
        except Exception as e:
            logger.error(f"Failed to generate social post: {e}")
            return safe_tool_error(e, "生成文案")
