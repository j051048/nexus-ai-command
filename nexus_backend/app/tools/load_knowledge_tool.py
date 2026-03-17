"""
Load Knowledge Tool — On-demand knowledge loading (P1b).

Two-layer knowledge architecture:
  Layer 1: System Prompt only contains a lightweight skill index
           (name + one-line description + trigger condition)
  Layer 2: Agent actively loads full knowledge content via this tool

This avoids bloating the system prompt with rarely-used knowledge
while giving the agent precise, purpose-driven access.
"""

import logging
from typing import Any

from app.tools.base_tool import BaseTool
from app.tools.registry import register_tool

logger = logging.getLogger(__name__)

# ── Knowledge Skill Index ──────────────────────────────────────────────────
# Layer 1: lightweight index injected into system prompt.
# Each entry: (skill_id, name, description, trigger_keywords)

KNOWLEDGE_SKILL_INDEX: list[dict[str, str]] = [
    {
        "id": "company_policy",
        "name": "公司政策制度",
        "description": "公司规章制度、考勤政策、请假规定、报销标准等",
        "triggers": "政策,制度,规定,规章,标准,流程,手册",
    },
    {
        "id": "product_docs",
        "name": "产品技术文档",
        "description": "产品参数、技术规格、使用手册、FAQ",
        "triggers": "产品,参数,规格,型号,技术,手册,说明书",
    },
    {
        "id": "sales_playbook",
        "name": "销售话术与策略",
        "description": "销售话术、客户应对策略、竞品对比、报价指南",
        "triggers": "话术,销售,报价,竞品,客户,策略,成交",
    },
    {
        "id": "industry_knowledge",
        "name": "行业知识",
        "description": "行业趋势、市场分析、法规标准、技术动态",
        "triggers": "行业,市场,趋势,法规,标准,动态,分析",
    },
    {
        "id": "onboarding",
        "name": "入职培训资料",
        "description": "新员工入职指南、系统使用教程、组织架构介绍",
        "triggers": "入职,培训,教程,指南,新员工,组织架构",
    },
]


def build_skill_index_prompt() -> str:
    """Build the lightweight skill index for system prompt injection (Layer 1).

    Returns a compact text block listing available knowledge domains.
    The agent reads this to decide when to call load_knowledge.
    """
    lines = ["[可用知识库 — 需要时用 load_knowledge 工具按需加载]"]
    for skill in KNOWLEDGE_SKILL_INDEX:
        lines.append(f"  • {skill['name']}: {skill['description']}")
    lines.append("[如需查询以上知识，请调用 load_knowledge 工具，传入相关 query]")
    return "\n".join(lines)


# Track loaded knowledge per session to avoid redundant loads
# Key: (user_id, session_id, query_hash) → True
_loaded_cache: dict[tuple[str, str, str], bool] = {}
_CACHE_MAX_SIZE = 200


def _query_hash(query: str) -> str:
    """Simple hash for dedup."""
    import hashlib
    return hashlib.md5(query.encode()).hexdigest()[:12]


@register_tool
class LoadKnowledgeTool(BaseTool):
    name = "load_knowledge"
    description = (
        "按需加载知识库内容。当你需要查询公司政策、产品文档、销售话术、"
        "行业知识等事实性信息时，使用此工具检索相关知识。"
        "同一会话中相同查询不会重复加载。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "要检索的问题或关键词",
            },
            "domain": {
                "type": "string",
                "enum": [s["id"] for s in KNOWLEDGE_SKILL_INDEX],
                "description": "知识域（可选，不指定则全域搜索）",
            },
        },
        "required": ["query"],
    }
    category = "knowledge"
    domain = "knowledge"

    async def execute(self, arguments: dict[str, Any], context: dict[str, Any] | None = None) -> str:
        ctx = context or {}
        user_id = ctx.get("user_id", "")
        session_id = ctx.get("session_id", "default")
        org_id = ctx.get("org_id")
        query = arguments.get("query", "").strip()

        if not query:
            return "错误：query 不能为空"

        # Dedup check — avoid redundant loads in same session
        cache_key = (user_id, session_id, _query_hash(query))
        if cache_key in _loaded_cache:
            return f"[知识已加载] 该查询在本会话中已检索过，请直接使用之前的结果。"

        try:
            from app.services.vector_service import vector_service

            result = await vector_service.search(
                query=query,
                user_id=user_id,
                org_id=org_id,
                limit=5,
            )

            # Mark as loaded
            if len(_loaded_cache) >= _CACHE_MAX_SIZE:
                # Evict oldest entries
                keys_to_remove = list(_loaded_cache.keys())[:_CACHE_MAX_SIZE // 2]
                for k in keys_to_remove:
                    _loaded_cache.pop(k, None)
            _loaded_cache[cache_key] = True

            if isinstance(result, str) and "未找到" in result:
                return f"知识库中未找到与「{query}」相关的内容。"

            return f"[知识库检索结果]\n{result}\n[检索结束]"

        except Exception as e:
            logger.error(f"[LoadKnowledge] Failed: {e}", exc_info=True)
            return f"知识库检索失败: {e}"
