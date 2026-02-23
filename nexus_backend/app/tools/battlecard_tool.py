from typing import Any

from app.services.vector_service import vector_service

from .base_tool import BaseTool


class BattlecardTool(BaseTool):
    name = "get_battlecard"
    description = "【销售赋能】获取竞争对手的实时打击卡（基于知识库 RAG）"

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

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        comp = args.get("competitor_name", "")
        if not comp:
            return "❌ 请指定竞争对手名称。"

        # P2 Implementation: Dynamic RAG instead of Hardcoded Dict
        # We query the Vector DB for info about this competitor

        query = f"竞争对手 {comp} 的劣势、弱点以及我们产品的对比优势"

        # Reuse the VectorService to get real data from uploaded documents
        # This assumes the user has uploaded competitor analysis docs
        rag_result = await vector_service.search(query, user_id, limit=2, config=config)

        if "No relevant documents" in rag_result or not rag_result:
            # Fallback to a generic template if knowledge base is empty, but warn the user
            return f"""
            ℹ️ 知识库中暂未找到关于 **{comp}** 的详细文档。

            ⚔️ **通用竞品打击策略建议 (Template)**:
            1. **性价比**: 强调我们的 TCO (全生命周期成本) 更低。
            2. **服务**: 突出我们 24 小时内的本地化响应速度。
            3. **定制化**: 询问客户是否有特殊需求，{comp} 作为大厂可能难以配合定制。

            *建议上传该对手的分析报告到知识库以获取更精准的 AI 建议。*
            """

        return f"⚔️ **{comp} 专属竞品打击卡** (基于知识库):\n\n{rag_result}"
