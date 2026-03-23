"""
search_long_term_memory_tool — Agent 主动长短期记忆检索工具 (Memory Interleave)。

支持 Agent 在对话或规划(WBS)阶段，遇到知识缺失时主动检索用户的偏好、事实或历史对话记忆，
实现多轮(Multi-hop)的记忆组合检索与推断。
"""

import logging
from typing import Any

from app.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class SearchLongTermMemoryTool(BaseTool):
    """主动在用户的长期记忆库和组织记忆库中搜索关联信息。"""

    domain = "system"
    requires_org_id = False

    @property
    def name(self) -> str:
        return "search_long_term_memory"

    @property
    def description(self) -> str:
        return (
            "检索用户长期记忆库和组织知识库中的偏好、事实或历史信息。\n"
            "使用场景:\n"
            "- 面临需要依赖用户过去背景知识或习惯来决策的情况\n"
            "- 需要多轮迭代结合多种记忆进行复合推断\n"
            "- 想要回忆先前存储或约定的工作流程\n"
            "参数说明:\n"
            "- query: 搜索关键词或短语，需简练、语义明确\n"
            "- category: 可选过滤类型 (preference, fact, explicit_memory, knowledge)\n"
        )

    @property
    def examples(self) -> list[dict]:
        return [
            {"input": {"query": "报告格式偏好", "category": "preference"}, "output_summary": "返回用户关于报告格式的偏好记忆"},
            {"input": {"query": "华为客户联系方式", "category": "all"}, "output_summary": "全类别检索与华为客户相关的记忆记录"},
        ]

    @property
    def related_tools(self) -> list[str]:
        return ["save_memory", "load_knowledge"]

    @property
    def gotchas(self) -> str:
        return "query 应简练且语义明确，避免过长句子；未指定 category 时默认搜索全部类别；个人记忆最多返回5条、组织记忆最多返回3条。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或短语",
                },
                "category": {
                    "type": "string",
                    "enum": ["preference", "fact", "explicit_memory", "knowledge", "all"],
                    "description": "检索的记忆分类过滤，如果不确定可以传 all 或省略",
                },
            },
            "required": ["query"],
        }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] | None = None) -> str:
        from app.services.conversation_memory_service import conversation_memory_service
        
        query = args["query"]
        category = args.get("category", "all")
        org_id = (config or {}).get("org_id")

        try:
            results = []
            
            # 搜索用户个人记忆
            memories = await conversation_memory_service.search_memories(
                user_id=user_id,
                query=query,
                limit=5,
                org_id=org_id,
            )
            
            if category and category != "all":
                memories = [m for m in memories if m.get("category") == category]
            
            if memories:
                results.append("[个人长期记忆]")
                for m in memories:
                    results.append(f"- [{m.get('category')}] {m.get('key', 'unknown')}: {m.get('value')}")

            # 搜索组织共享记忆 (Org Memory)
            if org_id:
                org_memories = await conversation_memory_service.search_org_memories(
                    org_id=org_id,
                    query=query,
                    limit=3,
                )
                if category and category != "all":
                    org_memories = [m for m in org_memories if m.get("category") == category]
                
                if org_memories:
                    results.append("[组织共享记忆]")
                    for m in org_memories:
                        results.append(f"- [{m.get('category')}] {m.get('key', 'unknown')}: {m.get('value')}")

            if not results:
                return f"未找到与 '{query}' 相关的记忆记录。你可以尝试更换关键词再次搜索。"
            
            logger.info(f"[SearchMemoryTool] Found {len(memories)} personal and {len(org_memories) if org_id else 0} org memories for query '{query}'")
            return "\n".join(results)

        except Exception as e:
            logger.warning(f"[SearchMemoryTool] Error searching memory: {e}")
            return f"⚠️ 记忆检索失败: {str(e)}"
