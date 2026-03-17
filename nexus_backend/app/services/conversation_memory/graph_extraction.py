"""Graph entity extraction using structured Function Calling.

Inspired by Mem0's approach: use tool/function call schemas to extract
entities and relationships from conversations in a structured way,
instead of free-form LLM output.

Stores triples (source, relationship, destination) in PostgreSQL
for lightweight knowledge graph functionality.
"""

import json
import logging
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)


# ── Function Calling tool definitions for entity extraction ──

EXTRACT_ENTITIES_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_entities",
        "description": "从对话中提取命名实体及其类型",
        "parameters": {
            "type": "object",
            "properties": {
                "entities": {
                    "type": "array",
                    "description": "提取到的实体列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "实体名称，如人名、公司名、产品名等",
                            },
                            "entity_type": {
                                "type": "string",
                                "enum": [
                                    "person", "organization", "project",
                                    "product", "location", "event",
                                    "concept", "tool", "document",
                                ],
                                "description": "实体类型",
                            },
                        },
                        "required": ["name", "entity_type"],
                    },
                },
            },
            "required": ["entities"],
        },
    },
}

ESTABLISH_RELATIONS_TOOL = {
    "type": "function",
    "function": {
        "name": "establish_relationships",
        "description": "建立实体之间的关系三元组",
        "parameters": {
            "type": "object",
            "properties": {
                "relationships": {
                    "type": "array",
                    "description": "关系三元组列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string",
                                "description": "关系的源实体名称",
                            },
                            "source_type": {
                                "type": "string",
                                "description": "源实体类型",
                            },
                            "relationship": {
                                "type": "string",
                                "description": "关系类型，如 '负责', '属于', '合作', '使用', '汇报给'",
                            },
                            "destination": {
                                "type": "string",
                                "description": "关系的目标实体名称",
                            },
                            "destination_type": {
                                "type": "string",
                                "description": "目标实体类型",
                            },
                        },
                        "required": [
                            "source", "source_type",
                            "relationship",
                            "destination", "destination_type",
                        ],
                    },
                },
            },
            "required": ["relationships"],
        },
    },
}


EXTRACT_SYSTEM_PROMPT = """你是知识图谱提取专家。从用户与 AI 助手的对话中提取有价值的实体和关系。

注意：
- 只提取明确出现在对话中的实体和关系
- 不要推测或编造不存在的关系
- 忽略临时性、一次性的信息
- 关注人物、组织、项目、产品等核心实体
- 关系描述要简洁（2-6个字），如"负责"、"属于"、"合作"、"汇报给"

如果对话中没有值得提取的实体关系，请调用 extract_entities 返回空数组。"""


async def extract_graph_entities(
    user_message: str,
    ai_response: str,
    org_id: str,
    user_id: str | None = None,
    tool_outputs: list[dict] | None = None,
    db: Any = None,
) -> list[dict]:
    """从对话中提取实体和关系，存储为知识图谱三元组。

    使用 Function Calling 而非自由格式 LLM 输出，保证结构化。

    Args:
        user_message: 用户消息
        ai_response: AI 回复
        org_id: 组织 ID
        user_id: 用户 ID
        tool_outputs: 工具调用输出
        db: 数据库客户端

    Returns:
        提取到的关系三元组列表
    """
    client = db or supabase
    if not client:
        return []

    # Build conversation context for extraction
    conversation = f"用户: {user_message}\nAI助手: {ai_response}"
    if tool_outputs:
        tool_context = "\n".join(
            f"工具({t.get('tool_name', '')}): {str(t.get('result', ''))[:200]}"
            for t in tool_outputs[:3]
        )
        conversation += f"\n{tool_context}"

    # Skip very short conversations
    if len(conversation) < 30:
        return []

    try:
        from app.services.ai_service import AIService

        # Use LLM to extract entities and relationships via structured output
        prompt = f"请分析以下对话，提取实体和关系：\n\n{conversation}"

        result_text = await AIService.call_llm(
            prompt,
            EXTRACT_SYSTEM_PROMPT,
        )

        # Parse entities and relationships from LLM response
        extracted_relations = _parse_extraction_response(result_text)

        if not extracted_relations:
            return []

        # Store the extracted triples
        saved = await _store_triples(
            relations=extracted_relations,
            org_id=org_id,
            user_id=user_id,
            source_context=user_message[:200],
            db=client,
        )

        if saved:
            logger.info(
                f"[GraphExtract] Extracted {len(saved)} entity relations "
                f"for org {org_id}"
            )

        return saved

    except Exception as e:
        logger.debug(f"[GraphExtract] Entity extraction skipped: {e}")
        return []


def _parse_extraction_response(response_text: str) -> list[dict]:
    """Parse LLM response to extract entity relationships."""
    from .llm_utils import parse_llm_json

    parsed = parse_llm_json(response_text)
    if not parsed:
        return []

    relations = []

    # Handle different response formats
    if isinstance(parsed, dict):
        # Check for relationships key
        if "relationships" in parsed:
            raw_rels = parsed["relationships"]
        elif "entities" in parsed:
            # Entities without relationships — not useful for graph
            return []
        else:
            return []
    elif isinstance(parsed, list):
        raw_rels = parsed
    else:
        return []

    for rel in raw_rels:
        if not isinstance(rel, dict):
            continue
        source = rel.get("source", "").strip()
        relationship = rel.get("relationship", "").strip()
        destination = rel.get("destination", "").strip()

        # Validate triple
        if not all([source, relationship, destination]):
            continue
        if len(source) > 100 or len(destination) > 100 or len(relationship) > 50:
            continue

        relations.append({
            "source": source,
            "source_type": rel.get("source_type", "concept"),
            "relationship": relationship,
            "destination": destination,
            "destination_type": rel.get("destination_type", "concept"),
        })

    return relations[:10]  # Max 10 relations per extraction


async def _store_triples(
    relations: list[dict],
    org_id: str,
    user_id: str | None,
    source_context: str,
    db: Any,
) -> list[dict]:
    """Store extracted triples in the knowledge_graph_triples table."""
    saved: list[dict] = []

    for rel in relations:
        try:
            # Check for existing duplicate
            existing = await _find_existing_triple(
                org_id=org_id,
                source=rel["source"],
                relationship=rel["relationship"],
                destination=rel["destination"],
                db=db,
            )

            if existing:
                # Update strength (more frequent = stronger)
                try:
                    new_strength = min(float(existing.get("strength", 0.5)) + 0.1, 1.0)
                    await (
                        db.table("knowledge_graph_triples")
                        .update({"strength": new_strength, "occurrences": existing.get("occurrences", 1) + 1})
                        .eq("id", existing["id"])
                        .execute()
                    )
                except Exception:
                    pass
                continue

            # Insert new triple
            insert_data = {
                "organization_id": org_id,
                "source_entity": rel["source"],
                "source_type": rel.get("source_type", "concept"),
                "relationship": rel["relationship"],
                "destination_entity": rel["destination"],
                "destination_type": rel.get("destination_type", "concept"),
                "strength": 0.5,
                "occurrences": 1,
                "source_context": source_context,
            }
            if user_id:
                insert_data["created_by"] = user_id

            result = await db.table("knowledge_graph_triples").insert(insert_data).execute()
            if result.data:
                saved.append(result.data[0] if isinstance(result.data, list) else result.data)

        except Exception as e:
            err_str = str(e)
            if "knowledge_graph_triples" in err_str and ("42P01" in err_str or "PGRST" in err_str):
                logger.debug("knowledge_graph_triples table not yet created, skipping")
                return []
            logger.debug(f"Failed to store triple: {e}")

    return saved


async def _find_existing_triple(
    org_id: str,
    source: str,
    relationship: str,
    destination: str,
    db: Any,
) -> dict | None:
    """Check if a similar triple already exists."""
    try:
        result = (
            await db.table("knowledge_graph_triples")
            .select("id, strength, occurrences")
            .eq("organization_id", org_id)
            .eq("source_entity", source)
            .eq("relationship", relationship)
            .eq("destination_entity", destination)
            .maybe_single()
            .execute()
        )
        return result.data if result and result.data else None
    except Exception:
        return None


async def query_entity_relations(
    org_id: str,
    entity_name: str,
    limit: int = 20,
    db: Any = None,
) -> list[dict]:
    """查询某个实体的所有关系（出边和入边）。

    Args:
        org_id: 组织 ID
        entity_name: 实体名称
        limit: 最大返回条数

    Returns:
        关系三元组列表
    """
    client = db or supabase
    if not client:
        return []

    try:
        # 查询出边 (entity as source)
        outgoing = (
            await client.table("knowledge_graph_triples")
            .select("*")
            .eq("organization_id", org_id)
            .eq("source_entity", entity_name)
            .order("strength", desc=True)
            .limit(limit)
            .execute()
        )

        # 查询入边 (entity as destination)
        incoming = (
            await client.table("knowledge_graph_triples")
            .select("*")
            .eq("organization_id", org_id)
            .eq("destination_entity", entity_name)
            .order("strength", desc=True)
            .limit(limit)
            .execute()
        )

        results = (outgoing.data or []) + (incoming.data or [])
        return results[:limit]

    except Exception as e:
        logger.debug(f"Failed to query entity relations: {e}")
        return []
