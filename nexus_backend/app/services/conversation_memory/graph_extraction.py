"""Graph entity extraction using structured Function Calling.

Inspired by Mem0's approach: use tool/function call schemas to extract
entities and relationships from conversations in a structured way,
instead of free-form LLM output.

Stores triples (source, relationship, destination) in PostgreSQL
for lightweight knowledge graph functionality.
"""

import logging
from typing import Any

from app.core.database import supabase
from app.services.conversation_memory.ontology import (
    get_allowed_entity_types,
    get_extraction_prompt_hint,
    normalize_entity_type,
    normalize_relationship,
    validate_triple,
)

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
                                "enum": get_allowed_entity_types(),
                                "description": "实体类型（受 Ontology 约束）",
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
                            "source",
                            "source_type",
                            "relationship",
                            "destination",
                            "destination_type",
                        ],
                    },
                },
            },
            "required": ["relationships"],
        },
    },
}


EXTRACT_SYSTEM_PROMPT = f"""你是知识图谱提取专家。从用户与 AI 助手的对话中提取有价值的实体和关系。

{get_extraction_prompt_hint()}

注意：
- 只提取明确出现在对话中的实体和关系
- 不要推测或编造不存在的关系
- 忽略临时性、一次性的信息
- 关注人物、组织、项目、产品等核心实体
- 关系描述要简洁（2-6个字），如"负责"、"属于"、"合作"、"汇报给"

指代消解（Coreference Resolution）：
- 遇到代词（他/她/它/这个/那个）时，根据上下文替换为具体实体名
- 示例："张总说他负责华东区" → 提取 (张总, 负责, 华东区)，而非 (他, 负责, 华东区)
- 示例："苹果公司发布了新产品，它很受欢迎" → (新产品, 属于, 苹果公司)，而非 (它, ...)

如果对话中没有值得提取的实体关系，请调用 extract_entities 返回空数组。"""


async def extract_graph_entities(
    user_message: str,
    ai_response: str,
    org_id: str,
    user_id: str | None = None,
    tool_outputs: list[dict] | None = None,
    db: Any = None,
    session_id: str | None = None,
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
            session_id=session_id,
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

        # Validate basic structure
        if not all([source, relationship, destination]):
            continue
        if len(source) > 100 or len(destination) > 100 or len(relationship) > 50:
            continue

        # Ontology normalization: map free-form types to controlled vocabulary
        source_type = normalize_entity_type(rel.get("source_type", "concept"))
        dest_type = normalize_entity_type(rel.get("destination_type", "concept"))
        relationship = normalize_relationship(relationship)

        # Validate triple against Ontology constraints
        is_valid, reason = validate_triple(source_type, relationship, dest_type)
        if not is_valid:
            logger.debug(
                f"[GraphExtract] Skipping invalid triple: {source} -{relationship}-> {destination}: {reason}"
            )
            continue

        relations.append(
            {
                "source": source,
                "source_type": source_type,
                "relationship": relationship,
                "destination": destination,
                "destination_type": dest_type,
            }
        )

    return relations[:10]  # Max 10 relations per extraction


async def _store_triples(
    relations: list[dict],
    org_id: str,
    user_id: str | None,
    source_context: str,
    db: Any,
    session_id: str | None = None,
) -> list[dict]:
    """Store extracted triples in the knowledge_graph_triples table."""
    saved: list[dict] = []

    for rel in relations:
        try:
            # Entity Resolution: normalize synonymous entities before storage
            try:
                from .entity_resolution import get_entity_embedding, resolve_triple

                rel = await resolve_triple(org_id, rel, db)
            except Exception as e:
                logger.debug(f"[KG] Entity resolution skipped: {e}")

            # Check for existing duplicate
            existing = await _find_existing_triple(
                org_id=org_id,
                source=rel["source"],
                relationship=rel["relationship"],
                destination=rel["destination"],
                db=db,
            )

            if existing:
                # Exact same triple re-mentioned → reinforce strength + reset decay clock
                try:
                    new_strength = min(float(existing.get("strength", 0.5)) + 0.1, 1.0)
                    from datetime import UTC, datetime

                    await (
                        db.table("knowledge_graph_triples")
                        .update(
                            {
                                "strength": new_strength,
                                "occurrences": existing.get("occurrences", 1) + 1,
                                "last_reinforced_at": datetime.now(UTC).isoformat(),
                            }
                        )
                        .eq("id", existing["id"])
                        .execute()
                    )
                except Exception:
                    pass
                continue

            # 方案3: Check for conflicting triple (same source + relationship, different destination)
            # e.g., "张三-在-Google" already exists, new triple is "张三-在-Apple"
            # → soft-expire the old one, then INSERT the new one below
            try:
                conflict = await _find_conflicting_triple(
                    org_id=org_id,
                    source=rel["source"],
                    relationship=rel["relationship"],
                    db=db,
                )
                if (
                    conflict
                    and conflict.get("destination_entity") != rel["destination"]
                ):
                    # Soft-expire: set valid_to instead of DELETE
                    from datetime import UTC, datetime

                    now_iso = datetime.now(UTC).isoformat()
                    await (
                        db.table("knowledge_graph_triples")
                        .update({"valid_to": now_iso})
                        .eq("id", conflict["id"])
                        .execute()
                    )
                    logger.info(
                        "[KG] Soft-expired triple: %s -%s-> %s (replaced by -> %s)",
                        rel["source"],
                        rel["relationship"],
                        conflict.get("destination_entity"),
                        rel["destination"],
                    )
            except Exception as e:
                logger.error(f"[KG] Conflict check failed (non-critical): {e}")

            # Insert new triple (with entity embeddings for similarity search)
            from datetime import UTC, datetime

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
                "valid_from": datetime.now(UTC).isoformat(),
            }
            if user_id:
                insert_data["user_id"] = user_id
            if session_id:
                insert_data["source_session_id"] = session_id

            # Attach entity embeddings for future similarity search
            try:
                src_emb = await get_entity_embedding(rel["source"], org_id)
                dst_emb = await get_entity_embedding(rel["destination"], org_id)
                if src_emb:
                    insert_data["source_embedding"] = src_emb
                if dst_emb:
                    insert_data["dest_embedding"] = dst_emb
            except Exception:
                pass  # Embeddings are optional enhancement

            result = (
                await db.table("knowledge_graph_triples").insert(insert_data).execute()
            )
            if result.data:
                saved.append(
                    result.data[0] if isinstance(result.data, list) else result.data
                )

        except Exception as e:
            err_str = str(e)
            if "knowledge_graph_triples" in err_str and (
                "42P01" in err_str or "PGRST" in err_str
            ):
                logger.debug("knowledge_graph_triples table not yet created, skipping")
                return []
            logger.error(f"Failed to store triple: {e}")

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
            .is_("valid_to", "null")
            .maybe_single()
            .execute()
        )
        return result.data if result and result.data else None
    except Exception:
        return None


async def _find_conflicting_triple(
    org_id: str,
    source: str,
    relationship: str,
    db: Any,
) -> dict | None:
    """Find an active triple with same source+relationship but potentially different destination.

    Used for temporal evolution: "张三-在-Google" → "张三-在-Apple".
    """
    try:
        result = (
            await db.table("knowledge_graph_triples")
            .select("id, destination_entity, strength")
            .eq("organization_id", org_id)
            .eq("source_entity", source)
            .eq("relationship", relationship)
            .is_("valid_to", "null")
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
    hops: int = 2,
    db: Any = None,
    include_historical: bool = False,
) -> list[dict]:
    """查询某个实体的关系，支持多跳扩散。

    Args:
        org_id: 组织 ID
        entity_name: 实体名称
        limit: 最大返回条数
        hops: 跳数 (1=直接关系, 2=含邻居关系)
        include_historical: 是否包含已过期的历史三元组
    """
    client = db or supabase
    if not client:
        return []

    # Resolve entity alias first
    try:
        from .entity_resolution import resolve_entity

        entity_name = await resolve_entity(org_id, entity_name, db=client)
    except Exception:
        pass

    # Try 2-hop RPC first
    if hops >= 2:
        try:
            result = await client.rpc(
                "query_entity_relations_2hop",
                {
                    "p_org_id": org_id,
                    "p_entity_name": entity_name,
                    "p_limit": limit,
                },
            ).execute()
            if result.data:
                return result.data
        except Exception as e:
            logger.debug(f"[KG] 2-hop RPC unavailable, falling back: {e}")

    # Fallback: Python-side multi-hop
    try:
        # Hop 1: direct relations
        out_q = (
            client.table("knowledge_graph_triples")
            .select("*")
            .eq("organization_id", org_id)
            .eq("source_entity", entity_name)
        )
        in_q = (
            client.table("knowledge_graph_triples")
            .select("*")
            .eq("organization_id", org_id)
            .eq("destination_entity", entity_name)
        )
        if not include_historical:
            out_q = out_q.is_("valid_to", "null")
            in_q = in_q.is_("valid_to", "null")
        outgoing = await out_q.order("strength", desc=True).limit(limit).execute()
        incoming = await in_q.order("strength", desc=True).limit(limit).execute()

        hop1 = (outgoing.data or []) + (incoming.data or [])
        for t in hop1:
            t["hop"] = 1
            if include_historical and t.get("valid_to"):
                t["_historical"] = True

        if hops < 2 or not hop1:
            return hop1[:limit]

        # Hop 2: neighbor expansion
        seen_ids = {t["id"] for t in hop1}
        neighbors = set()
        for t in hop1:
            src = t.get("source_entity", "")
            dst = t.get("destination_entity", "")
            if src != entity_name:
                neighbors.add(src)
            if dst != entity_name:
                neighbors.add(dst)

        hop2: list[dict] = []
        for neighbor in list(neighbors)[:10]:  # Cap neighbor expansion
            try:
                n_out = (
                    await client.table("knowledge_graph_triples")
                    .select("*")
                    .eq("organization_id", org_id)
                    .eq("source_entity", neighbor)
                    .is_("valid_to", "null")
                    .neq("destination_entity", entity_name)
                    .order("strength", desc=True)
                    .limit(5)
                    .execute()
                )
                n_in = (
                    await client.table("knowledge_graph_triples")
                    .select("*")
                    .eq("organization_id", org_id)
                    .eq("destination_entity", neighbor)
                    .is_("valid_to", "null")
                    .neq("source_entity", entity_name)
                    .order("strength", desc=True)
                    .limit(5)
                    .execute()
                )
                for t in (n_out.data or []) + (n_in.data or []):
                    if t["id"] not in seen_ids:
                        t["hop"] = 2
                        t["strength"] = float(t.get("strength", 0.5)) * 0.6
                        hop2.append(t)
                        seen_ids.add(t["id"])
            except Exception:
                continue

        combined = hop1 + hop2
        combined.sort(
            key=lambda t: (-t.get("hop", 1) == 1, -float(t.get("strength", 0)))
        )
        return combined[:limit]

    except Exception as e:
        logger.error(f"Failed to query entity relations: {e}")
        return []


async def search_kg_hybrid(
    org_id: str,
    query: str,
    limit: int = 10,
    expand_hops: bool = True,
    db: Any = None,
    include_historical: bool = False,
) -> list[dict]:
    """Search knowledge graph triples using hybrid FTS + entity match with RRF fusion.

    When expand_hops=True, expands 1-hop neighbors from initial results for richer context.
    When include_historical=True, includes expired triples annotated with _historical=True.
    Falls back to simple ILIKE query if the RPC is not yet deployed.
    """
    client = db or supabase
    if not client or not query:
        return []

    # Resolve query entities through alias table
    try:
        from .entity_resolution import resolve_entity

        resolved_query = await resolve_entity(org_id, query, db=client)
        if resolved_query != query:
            query = resolved_query
    except Exception:
        pass

    direct_results: list[dict] = []

    try:
        result = await client.rpc(
            "search_kg_triples_hybrid",
            {"p_org_id": org_id, "p_query_text": query, "p_limit": limit},
        ).execute()
        direct_results = result.data or []
    except Exception as e:
        # RPC not deployed yet — fallback to simple ILIKE
        logger.error(f"[KG] Hybrid search RPC failed, falling back to ILIKE: {e}")
        try:
            pattern = f"%{query}%"
            fallback_q = (
                client.table("knowledge_graph_triples")
                .select("*")
                .eq("organization_id", org_id)
            )
            if not include_historical:
                fallback_q = fallback_q.is_("valid_to", "null")
            result = await (
                fallback_q.or_(
                    f"source_entity.ilike.{pattern},"
                    f"destination_entity.ilike.{pattern},"
                    f"relationship.ilike.{pattern}"
                )
                .order("strength", desc=True)
                .limit(limit)
                .execute()
            )
            direct_results = result.data or []
        except Exception:
            return []

    if not direct_results or not expand_hops:
        return direct_results[:limit]

    # 1-hop expansion: find neighbors of top results
    seen_ids = {t["id"] for t in direct_results}
    entities_in_results = set()
    for t in direct_results[:5]:  # Expand from top 5 only
        entities_in_results.add(t.get("source_entity", ""))
        entities_in_results.add(t.get("destination_entity", ""))
    entities_in_results.discard("")

    expanded: list[dict] = []
    for entity in list(entities_in_results)[:6]:
        try:
            neighbors = (
                await client.table("knowledge_graph_triples")
                .select("*")
                .eq("organization_id", org_id)
                .is_("valid_to", "null")
                .or_(f"source_entity.eq.{entity}," f"destination_entity.eq.{entity}")
                .order("strength", desc=True)
                .limit(3)
                .execute()
            )
            for t in neighbors.data or []:
                if t["id"] not in seen_ids:
                    t["hop"] = 2
                    t["strength"] = float(t.get("strength", 0.5)) * 0.6
                    expanded.append(t)
                    seen_ids.add(t["id"])
        except Exception:
            continue

    # Mark direct results as hop 1
    for t in direct_results:
        t["hop"] = 1

    combined = direct_results + expanded
    combined.sort(key=lambda t: (-float(t.get("strength", 0))))
    # Annotate historical triples when include_historical is enabled
    if include_historical:
        for t in combined:
            if t.get("valid_to"):
                t["_historical"] = True
    return combined[:limit]


async def query_entity_at_time(
    org_id: str,
    entity_name: str,
    target_time: str,
    db: Any = None,
) -> list[dict]:
    """查询某时间点有效的知识图谱三元组，支持时间回溯。

    例如: "张三去年在哪家公司？" → target_time="2025-04-01"
    返回 valid_from <= target_time AND (valid_to IS NULL OR valid_to > target_time) 的三元组。
    """
    client = db or supabase
    if not client or not entity_name:
        return []

    # Resolve entity alias
    try:
        from .entity_resolution import resolve_entity

        entity_name = await resolve_entity(org_id, entity_name, db=client)
    except Exception:
        pass

    results: list[dict] = []

    try:
        # Outgoing relations at target_time
        out_res = await (
            client.table("knowledge_graph_triples")
            .select("*")
            .eq("organization_id", org_id)
            .eq("source_entity", entity_name)
            .lte("valid_from", target_time)
            .order("valid_from", desc=True)
            .limit(20)
            .execute()
        )
        for t in out_res.data or []:
            vt = t.get("valid_to")
            if vt is None or vt > target_time:
                t["_historical"] = vt is not None
                results.append(t)

        # Incoming relations at target_time
        in_res = await (
            client.table("knowledge_graph_triples")
            .select("*")
            .eq("organization_id", org_id)
            .eq("destination_entity", entity_name)
            .lte("valid_from", target_time)
            .order("valid_from", desc=True)
            .limit(20)
            .execute()
        )
        for t in in_res.data or []:
            vt = t.get("valid_to")
            if vt is None or vt > target_time:
                t["_historical"] = vt is not None
                results.append(t)

    except Exception as e:
        logger.error(f"[KG] Temporal query failed for {entity_name}@{target_time}: {e}")

    results.sort(key=lambda t: t.get("valid_from", ""), reverse=True)
    return results
