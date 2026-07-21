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

from app.tools._shared import safe_tool_error
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


# Track successful evidence per session to avoid redundant embedding calls.
# Failed/empty retrievals are deliberately not cached so a newly indexed
# document can be found immediately on retry.
_loaded_cache: dict[tuple[str, str, str], str] = {}
_CACHE_MAX_SIZE = 200


def _query_hash(query: str) -> str:
    """Simple hash for dedup."""
    import hashlib

    return hashlib.md5(query.encode()).hexdigest()[:12]


@register_tool(
    name="load_knowledge", category="knowledge", description="加载知识库技能详情"
)
class LoadKnowledgeTool(BaseTool):
    name = "load_knowledge"
    description = (
        "按文件名、型号、问题或关键词检索企业资料正文，支持公司政策、产品文档、"
        "既有方案、投标文件、销售话术与行业知识。"
        "当需要查询事实性信息且长期记忆中未找到时调用。"
        "用户提到‘之前那个文件/方案’或具体型号时也必须调用。"
    )
    examples = [
        {
            "input": {"query": "客户报价审批流程", "domain": "company_policy"},
            "output_summary": "从公司政策知识库中检索报价审批相关内容",
        },
        {
            "input": {"query": "产品A的技术参数"},
            "output_summary": "全域搜索产品A的技术参数信息",
        },
    ]
    related_tools = ["search_long_term_memory", "web_search"]
    gotchas = "只缓存成功证据；重复查询会回放原证据。文件名和型号可直接检索，domain 仅用于表达检索目的，不会误删其他资料。"
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

    async def execute(
        self, arguments: dict[str, Any], context: dict[str, Any] | None = None
    ) -> str:
        ctx = context or {}
        user_id = ctx.get("user_id", "")
        session_id = ctx.get("session_id", "default")
        org_id = ctx.get("org_id")
        query = arguments.get("query", "").strip()
        domain = arguments.get("domain", "").strip()

        if not query:
            return "错误：query 不能为空"
        if not org_id:
            return "知识库检索失败：缺少企业组织信息，请重新登录后再试。"

        cache_key = (user_id, session_id, _query_hash(f"{domain}:{query}"))
        if cache_key in _loaded_cache:
            return _loaded_cache[cache_key]

        try:
            from app.services.vector_service import vector_service

            rows = await vector_service.search_evidence(
                query=query,
                user_id=user_id,
                org_id=org_id,
                limit=6,
            )
            if not rows:
                return f"知识库中未找到与「{query}」相关的内容。"

            evidence_lines = []
            for row in rows:
                document_id = str(row.get("document_id") or "")
                chunk_id = str(row.get("chunk_id") or row.get("id") or "")
                title = str(
                    row.get("name")
                    or row.get("title")
                    or row.get("source")
                    or "企业资料"
                )
                excerpt = str(row.get("excerpt") or row.get("content") or "")[:1400]
                citation = (
                    f"EVID:{document_id}:{chunk_id}"
                    if document_id and chunk_id
                    else "EVID:待核验"
                )
                evidence_lines.append(f"[{citation}] {title}\n{excerpt}")

            purpose = f"（检索目的：{domain}）" if domain else ""
            result = (
                f"[企业资料检索结果]{purpose}\n"
                + "\n\n---\n\n".join(evidence_lines)
                + "\n[检索结束：回答或生成文件时必须标注上述来源，不得声称未找到。]"
            )
            if len(_loaded_cache) >= _CACHE_MAX_SIZE:
                keys_to_remove = list(_loaded_cache.keys())[: _CACHE_MAX_SIZE // 2]
                for key in keys_to_remove:
                    _loaded_cache.pop(key, None)
            _loaded_cache[cache_key] = result
            return result

        except Exception as e:
            logger.error(f"[LoadKnowledge] Failed: {e}", exc_info=True)
            return safe_tool_error(e, "知识库检索")

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        return await self.execute(args, {"user_id": user_id, **(config or {})})
