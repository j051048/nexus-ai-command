"""
VMD 投标工具集 (Virtual Marketing Department - Tender/Bid Tools)

工作项 #29: 为 clue_agent 和 content_agent 提供投标文件处理能力
- 投标文件初稿生成
- 技术偏离表生成
- 投标合规性校验
- 招标要求提取
"""

import logging
from typing import Any

from app.services.ai_service import AIService
from app.services.vector_service import vector_service
from app.tools._shared import safe_tool_error

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  投标文件生成工具
# ═══════════════════════════════════════════════════════════════════════════════


class GenerateBidDocumentTool(BaseTool):
    """基于招标要求生成投标文件初稿框架"""

    name = "generate_bid_document"
    domain = "tender"
    description = "根据招标要求生成投标文件初稿框架，含技术方案、商务报价和资质证明等章节。当用户说'写投标文件'、'准备投标书'、'生成标书'时调用。"
    required_role = "all"
    examples = [
        {
            "input": {
                "project_name": "某高校实验室设备采购",
                "our_products": "ICP-MS 7800",
                "budget_range": "50-80万元",
            },
            "output_summary": "生成ICP-MS投标文件框架，含技术方案和商务报价章节",
        },
        {
            "input": {
                "project_name": "环保监测站仪器招标",
                "tender_requirements": "需具备CMA资质",
                "deadline": "2026-04-15",
            },
            "output_summary": "生成环保监测招标的完整投标文件框架",
        },
    ]
    related_tools = [
        "generate_deviation_table",
        "check_bid_compliance",
        "extract_bid_requirements",
    ]
    gotchas = "生成的是框架和要点，非最终投标文件。技术参数来自知识库检索，未找到的会标注'待补充'。"

    parameters = {
        "type": "object",
        "properties": {
            "project_name": {
                "type": "string",
                "description": "招标项目名称",
            },
            "tender_requirements": {
                "type": "string",
                "description": "招标文件关键要求摘要",
            },
            "our_products": {
                "type": "string",
                "description": "我方拟投标的产品/方案名称",
            },
            "budget_range": {
                "type": "string",
                "description": "项目预算范围（如：50-80万元）",
            },
            "deadline": {
                "type": "string",
                "description": "投标截止日期",
            },
        },
        "required": ["project_name"],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        project_name = args.get("project_name", "").strip()
        if not project_name:
            return "❌ 请提供招标项目名称。"

        tender_requirements = args.get("tender_requirements", "")
        our_products = args.get("our_products", "")
        budget_range = args.get("budget_range", "")
        deadline = args.get("deadline", "")

        # Search knowledge base for product specs and past bid documents
        kb_context = ""
        try:
            org_id = config.get("org_id") if config else None
            search_query = f"{our_products or project_name} 技术参数 投标 方案".strip()
            kb_result = await vector_service.search(
                search_query,
                user_id,
                limit=5,
                config=config,
                org_id=org_id,
            )
            if kb_result and "No relevant documents" not in kb_result:
                kb_context = f"\n\n## 知识库参考（产品资料/历史标书）\n{kb_result}"
        except Exception as e:
            logger.warning(f"Knowledge base search failed for bid document: {e}")

        prompt = (
            f"请为以下招标项目生成投标文件初稿框架：\n\n"
            f"- 项目名称：{project_name}\n"
            f"- 招标要求：{tender_requirements or '待补充'}\n"
            f"- 拟投产品/方案：{our_products or '待确定'}\n"
            f"- 预算范围：{budget_range or '未知'}\n"
            f"- 截止日期：{deadline or '未知'}\n"
            f"{kb_context}\n\n"
            f"请按标准投标文件格式生成框架：\n"
            f"1. **投标函** — 致招标人函、投标承诺\n"
            f"2. **资格证明文件** — 企业资质清单、业绩证明\n"
            f"3. **技术方案** — 技术路线、产品配置、系统架构\n"
            f"4. **实施方案** — 项目计划、验收标准、培训计划\n"
            f"5. **售后服务** — 质保方案、响应时间、备件策略\n"
            f"6. **商务报价** — 报价构成、分项清单、付款条件\n"
            f"7. **技术偏离表** — 需要标注偏离的指标\n"
            f"8. **附件** — 需要准备的证明文件清单\n\n"
            f"对每个章节提供具体的内容要点和注意事项。"
        )

        system = (
            "你是科学仪器行业投标专家，熟悉政府和企业采购招投标流程。"
            "请生成规范的投标文件框架，重点关注技术响应的完整性和合规性。"
            "标注可能的废标风险点，并给出规避建议。中文输出。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            return self.format_result(
                data={}, summary=f"**投标文件框架 — {project_name}**\n\n{result}"
            )
        except Exception as e:
            logger.error(f"Failed to generate bid document: {e}")
            return safe_tool_error(e, "生成投标文件")


# ═══════════════════════════════════════════════════════════════════════════════
#  技术偏离表生成工具
# ═══════════════════════════════════════════════════════════════════════════════


class GenerateDeviationTableTool(BaseTool):
    """生成技术偏离表"""

    name = "generate_deviation_table"
    domain = "tender"
    description = "生成技术偏离表，逐项对照招标技术要求与我方产品参数。当用户说'偏离表'、'技术对比'、'参数对照'时调用。"
    required_role = "all"
    examples = [
        {
            "input": {
                "tender_specs": "检出限≤0.1ppb，线性范围1-1000ppb",
                "our_product": "ICP-MS 7800",
            },
            "output_summary": "生成ICP-MS与招标参数的逐项偏离对比表",
        },
        {
            "input": {
                "tender_specs": "分辨率≥0.5nm，波长范围190-1100nm",
                "our_product": "UV-2600",
                "our_specs": "分辨率0.3nm，波长范围185-1100nm",
            },
            "output_summary": "生成含正偏离标注的紫外分光光度计偏离表",
        },
    ]
    related_tools = [
        "generate_bid_document",
        "check_bid_compliance",
        "extract_bid_requirements",
    ]
    gotchas = "tender_specs为必填，应逐项列出招标参数。我方参数优先从知识库检索，our_specs可手动补充。偏离表用Markdown表格输出。"

    parameters = {
        "type": "object",
        "properties": {
            "tender_specs": {
                "type": "string",
                "description": "招标文件中的技术参数要求（逐项列出）",
            },
            "our_product": {
                "type": "string",
                "description": "我方产品名称或型号",
            },
            "our_specs": {
                "type": "string",
                "description": "我方产品技术参数（如有）",
            },
        },
        "required": ["tender_specs"],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        tender_specs = args.get("tender_specs", "").strip()
        if not tender_specs:
            return "❌ 请提供招标技术参数要求。"

        our_product = args.get("our_product", "")
        our_specs = args.get("our_specs", "")

        # Search knowledge base for our product specs
        kb_context = ""
        if our_product:
            try:
                org_id = config.get("org_id") if config else None
                kb_result = await vector_service.search(
                    f"{our_product} 技术参数 规格 指标",
                    user_id,
                    limit=5,
                    config=config,
                    org_id=org_id,
                )
                if kb_result and "No relevant documents" not in kb_result:
                    kb_context = f"\n\n## 我方产品资料（知识库）\n{kb_result}"
            except Exception as e:
                logger.warning(f"Knowledge base search failed for deviation table: {e}")

        prompt = (
            f"请生成技术偏离表：\n\n"
            f"## 招标技术要求\n{tender_specs}\n\n"
            f"## 我方产品：{our_product or '待确定'}\n"
            f"## 我方参数：{our_specs or '请参考知识库资料'}\n"
            f"{kb_context}\n\n"
            f"请按以下格式输出偏离表：\n"
            f"| 序号 | 招标要求 | 招标参数 | 我方响应 | 偏离情况 | 说明 |\n"
            f"|------|----------|----------|----------|----------|------|\n\n"
            f"偏离情况分为：\n"
            f"- ✅ 完全满足\n"
            f"- ⬆️ 正偏离（优于要求）\n"
            f"- ⚠️ 负偏离（低于要求，需说明原因和替代方案）\n"
            f"- ❌ 无法满足\n\n"
            f"最后请汇总偏离统计和整体评估。"
        )

        system = (
            "你是科学仪器投标技术专家。请严格对照招标要求逐项分析，"
            "对于负偏离项需要给出合理的解释和替代方案建议。"
            "格式使用 Markdown 表格，确保清晰易读。中文输出。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            return self.format_result(data={}, summary=f"**技术偏离表**\n\n{result}")
        except Exception as e:
            logger.error(f"Failed to generate deviation table: {e}")
            return safe_tool_error(e, "生成偏离表")


# ═══════════════════════════════════════════════════════════════════════════════
#  投标合规性校验工具
# ═══════════════════════════════════════════════════════════════════════════════


class CheckBidComplianceTool(BaseTool):
    """校验投标文件合规性"""

    name = "check_bid_compliance"
    domain = "tender"
    description = "校验投标文件的合规性，识别废标风险点并给出整改建议。当用户说'检查投标文件'、'合规检查'、'废标风险'时调用。"
    required_role = "all"
    examples = [
        {
            "input": {
                "bid_content": "投标文件技术方案章节内容...",
                "tender_requirements": "须具备ISO9001认证",
            },
            "output_summary": "返回合规性检查报告，标注资质缺失等高风险项",
        },
        {
            "input": {
                "bid_content": "商务报价部分内容...",
                "check_items": "价格格式,付款条件",
            },
            "output_summary": "返回聚焦商务条件的合规检查结果",
        },
    ]
    related_tools = [
        "generate_bid_document",
        "generate_deviation_table",
        "extract_bid_requirements",
    ]
    gotchas = "bid_content会被截断到前5000字符以防超出模型限制。检查结果按风险等级分为高/中/低三级。"

    parameters = {
        "type": "object",
        "properties": {
            "bid_content": {
                "type": "string",
                "description": "投标文件内容（关键章节）",
            },
            "tender_requirements": {
                "type": "string",
                "description": "招标文件的关键合规要求",
            },
            "check_items": {
                "type": "string",
                "description": "重点检查项（如：资质要求、技术参数、商务条件）",
            },
        },
        "required": ["bid_content"],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        bid_content = args.get("bid_content", "").strip()
        if not bid_content:
            return "❌ 请提供投标文件内容。"

        tender_requirements = args.get("tender_requirements", "")
        check_items = args.get("check_items", "")

        prompt = (
            f"请对以下投标文件进行合规性校验：\n\n"
            f"## 投标文件内容\n{bid_content[:5000]}\n\n"
            f"## 招标合规要求\n{tender_requirements or '请按通用招投标规范检查'}\n\n"
            f"## 重点检查项\n{check_items or '全面检查'}\n\n"
            f"请从以下维度进行检查：\n"
            f"1. **资格符合性** — 企业资质、业绩要求是否满足\n"
            f"2. **技术响应完整性** — 是否逐项响应了所有技术要求\n"
            f"3. **商务合规性** — 报价格式、付款条件、有效期是否合规\n"
            f"4. **文件完整性** — 签章、密封、份数等形式要求\n"
            f"5. **否决性条款** — 是否触犯了否决性（废标）条款\n"
            f"6. **常见陷阱** — 隐含的限制性条款或定向性条款\n\n"
            f"对每个问题标注风险等级：🔴高风险（可能废标）| 🟡中风险 | 🔵低风险\n"
            f"最后给出总体合规评分和整改建议清单。"
        )

        system = (
            "你是资深招投标合规审查专家，熟悉《政府采购法》《招标投标法》及相关法规。"
            "请严格审查投标文件，重点识别废标风险。"
            "对发现的问题给出具体的修改建议。中文输出。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            return self.format_result(
                data={}, summary=f"**投标合规性检查报告**\n\n{result}"
            )
        except Exception as e:
            logger.error(f"Failed to check bid compliance: {e}")
            return safe_tool_error(e, "合规检查")


# ═══════════════════════════════════════════════════════════════════════════════
#  招标要求提取工具
# ═══════════════════════════════════════════════════════════════════════════════


class ExtractBidRequirementsTool(BaseTool):
    """从招标文件中提取关键要求清单"""

    name = "extract_bid_requirements"
    domain = "tender"
    description = "从招标文件中提取关键要求清单，含资质要求、技术参数、商务条件和评分标准。当用户说'分析招标文件'、'提取要求'、'读招标书'时调用。"
    required_role = "all"
    examples = [
        {
            "input": {"tender_text": "招标文件全文或关键段落..."},
            "output_summary": "提取资质门槛、技术参数、评分标准等结构化要求清单",
        },
        {
            "input": {
                "tender_text": "招标文件内容...",
                "focus_areas": "技术参数,评分标准",
            },
            "output_summary": "聚焦技术参数和评分标准的提取结果",
        },
    ]
    related_tools = [
        "generate_bid_document",
        "generate_deviation_table",
        "check_bid_compliance",
    ]
    gotchas = "tender_text会被截断到前8000字符。输入过长时建议只粘贴关键章节。focus_areas可缩小提取范围提高精准度。"

    parameters = {
        "type": "object",
        "properties": {
            "tender_text": {
                "type": "string",
                "description": "招标文件内容（全文或关键段落）",
            },
            "focus_areas": {
                "type": "string",
                "description": "重点关注的领域（如：技术参数、资质门槛、评分标准）",
            },
        },
        "required": ["tender_text"],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        tender_text = args.get("tender_text", "").strip()
        if not tender_text:
            return "❌ 请提供招标文件内容。"

        # Truncate to prevent oversized LLM prompts
        tender_text = tender_text[:8000]
        focus_areas = args.get("focus_areas", "")[:500]

        prompt = (
            f"请从以下招标文件中提取关键要求清单：\n\n"
            f"## 招标文件内容\n{tender_text[:6000]}\n\n"
            f"## 重点关注\n{focus_areas or '全面提取'}\n\n"
            f"请按以下分类提取：\n"
            f"1. **资质门槛** — 必须满足的资格条件（废标项标红）\n"
            f"2. **技术参数** — 核心技术指标要求（标注是否为关键参数）\n"
            f"3. **商务条件** — 价格、付款、交付、质保要求\n"
            f"4. **评分标准** — 评分项和分值分布\n"
            f"5. **时间节点** — 投标截止、开标、交付等关键日期\n"
            f"6. **特殊要求** — 样品、演示、实地考察等\n"
            f"7. **否决性条款** — 触犯即废标的条款\n"
            f"8. **定向性分析** — 是否存在针对特定品牌的倾向性条款\n\n"
            f"请对每项要求标注优先级和我方应对建议。"
        )

        system = (
            "你是科学仪器行业资深投标顾问。请精确提取招标文件中的各类要求，"
            "特别关注否决性条款和评分权重较高的项目。"
            "用结构化格式输出，方便投标团队快速把握重点。中文输出。"
        )

        try:
            result = await AIService.call_llm(prompt, system)
            return self.format_result(
                data={}, summary=f"**招标要求提取清单**\n\n{result}"
            )
        except Exception as e:
            logger.error(f"Failed to extract bid requirements: {e}")
            return safe_tool_error(e, "提取招标要求")
