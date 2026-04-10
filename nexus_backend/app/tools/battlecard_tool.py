import logging
from typing import Any

from app.services.competitor_service import competitor_service
from app.services.vector_service import vector_service

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class BattlecardTool(BaseTool):
    name = "get_battlecard"
    domain = "tender"
    description = "获取指定竞争对手的实时打击卡，含结构化数据和知识库补充"
    examples = [
        {
            "input": {"competitor_name": "安捷伦"},
            "output_summary": "返回安捷伦的竞品打击卡，含优劣势、产品对比和打击策略",
        },
        {
            "input": {"competitor_name": "赛默飞"},
            "output_summary": "返回赛默飞的竞品打击卡及知识库中的相关分析",
        },
    ]
    gotchas = "竞品名称需与系统中录入的名称匹配。未录入的竞品仅返回通用策略建议。"
    related_tools = ["list_competitors"]

    parameters = {
        "type": "object",
        "properties": {
            "competitor_name": {
                "type": "string",
                "description": "竞争对手名称，如：安捷伦, 赛默飞",
            }
        },
        "required": ["competitor_name"],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        comp = args.get("competitor_name", "")
        if not comp:
            return "❌ 请指定竞争对手名称。"

        org_id = (config or {}).get("org_id")
        db = (config or {}).get("db")

        # 1. Try to find structured competitor data
        structured = None
        if db and org_id:
            try:
                match = await competitor_service.find_by_name(comp, org_id, db=db)
                if match:
                    structured = await competitor_service.get_battlecard_data(
                        match["id"], db=db
                    )
            except Exception as e:
                logger.warning(f"Structured competitor lookup failed: {e}")

        # 2. RAG search for additional context
        query = f"竞争对手 {comp} 的劣势、弱点以及我们产品的对比优势"
        rag_result = await vector_service.search(
            query, user_id, limit=2, config=config, org_id=org_id
        )
        has_rag = rag_result and "No relevant documents" not in rag_result

        # 3. Format output
        if structured:
            return self._format_structured_card(
                structured, rag_result if has_rag else None
            )

        if has_rag:
            return f"⚔️ **{comp} 专属竞品打击卡** (基于知识库):\n\n{rag_result}"

        return (
            f"ℹ️ 知识库中暂未找到关于 **{comp}** 的详细文档。\n\n"
            f"⚔️ **通用竞品打击策略建议**:\n"
            f"1. **性价比**: 强调我们的 TCO (全生命周期成本) 更低。\n"
            f"2. **服务**: 突出我们 24 小时内的本地化响应速度。\n"
            f"3. **定制化**: 询问客户是否有特殊需求，{comp} 作为大厂可能难以配合定制。\n\n"
            f"*建议管理员在【竞品打击库】中录入该对手的信息，或上传分析报告到知识库。*"
        )

    @staticmethod
    def _format_structured_card(data: dict, rag_context: str | None) -> str:
        c = data["competitor"]
        products = data.get("products", [])
        features = data.get("features", [])

        parts = [f"⚔️ **{c['name']}** 专属竞品打击卡"]

        if c.get("tag"):
            parts[0] += f"  `{c['tag']}`"
        if c.get("threat_level") and c["threat_level"] != "medium":
            level_map = {"low": "🟢低", "high": "🟠高", "critical": "🔴极高"}
            parts.append(
                f"威胁等级: {level_map.get(c['threat_level'], c['threat_level'])}"
            )

        parts.append("")

        if c.get("strength_summary"):
            parts.append(f"**对手优势**: {c['strength_summary']}")
        if c.get("weakness_summary"):
            parts.append(f"**对手劣势**: {c['weakness_summary']}")

        if products:
            parts.append("\n📦 **竞品产品**:")
            for p in products[:5]:
                line = f"- **{p['name']}**"
                if p.get("model"):
                    line += f" ({p['model']})"
                if p.get("price_range"):
                    line += f" | 价格: {p['price_range']}"
                if p.get("our_competing_product"):
                    line += f" | 我方对标: {p['our_competing_product']}"
                parts.append(line)

        if features:
            parts.append("\n📊 **维度对比**:")
            parts.append("| 维度 | 对手 | 我方 | 打击策略 |")
            parts.append("|------|------|------|----------|")
            for f in features:
                cs = (
                    f"{'⭐' * (f.get('competitor_score') or 0)}"
                    if f.get("competitor_score")
                    else "-"
                )
                os = (
                    f"{'⭐' * (f.get('our_score') or 0)}" if f.get("our_score") else "-"
                )
                strategy = (f.get("counter_strategy") or "-")[:50]
                parts.append(f"| {f['dimension']} | {cs} | {os} | {strategy} |")

        if rag_context:
            parts.append(f"\n📚 **知识库补充信息**:\n{rag_context}")

        return "\n".join(parts)


class ListCompetitorsTool(BaseTool):
    name = "list_competitors"
    domain = "tender"
    description = "列出当前租户已录入的所有竞品公司"
    examples = [
        {"input": {}, "output_summary": "返回所有已录入竞品的名称、标签和威胁等级列表"},
    ]
    gotchas = "需要组织信息才能查询。返回结果包含威胁等级标识。"
    related_tools = ["get_battlecard"]

    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        org_id = (config or {}).get("org_id")
        db = (config or {}).get("db")

        if not db or not org_id:
            return "❌ 无法获取组织信息，请检查配置。"

        try:
            competitors = await competitor_service.list_competitors(org_id, db=db)
        except Exception as e:
            logger.warning(f"List competitors tool failed: {e}")
            return "❌ 获取竞品列表失败，请稍后再试。"

        if not competitors:
            return "📋 当前还未录入竞品信息。管理员可在【竞品打击库】页面添加竞争对手。"

        lines = ["📋 **已录入竞品列表**:\n"]
        for i, c in enumerate(competitors, 1):
            line = f"{i}. **{c['name']}**"
            if c.get("tag"):
                line += f"  `{c['tag']}`"
            if c.get("threat_level") and c["threat_level"] != "medium":
                level_map = {"low": "🟢", "high": "🟠", "critical": "🔴"}
                line += f" {level_map.get(c['threat_level'], '')}"
            lines.append(line)

        lines.append(f"\n共 {len(competitors)} 家竞品。输入竞品名称可获取详细打击卡。")
        return "\n".join(lines)
