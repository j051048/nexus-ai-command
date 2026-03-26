"""Memory consolidation ("sleep cycle") and connection building."""

import logging
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)


async def consolidate_user_memories(
    user_id: str,
    org_id: str | None = None,
    batch_size: int = 30,
    db: Any = None,
) -> dict:
    """Consolidate a user's unconsolidated memories into cross-memory insights.

    Inspired by Google's Always-On Memory Agent "sleep cycle":
    1. Reads unconsolidated memories
    2. LLM discovers patterns, summaries, contradictions
    3. Stores insights in memory_consolidations table
    4. Builds connections between related memories
    5. Marks source memories as consolidated

    Returns: {"user_id": str, "processed": int, "insights_created": int}
    """
    from app.services.ai_service import AIService

    from .llm_utils import parse_llm_json

    client = db or supabase
    if not client:
        return {"user_id": user_id, "processed": 0, "insights_created": 0}

    try:
        result = (
            await client.table("conversation_memories")
            .select("id, category, key, value, importance")
            .eq("user_id", user_id)
            .eq("is_consolidated", False)
            .order("importance", desc=True)
            .limit(batch_size)
            .execute()
        )
    except Exception as e:
        logger.warning(f"Consolidation query failed for user {user_id}: {e}")
        return {"user_id": user_id, "processed": 0, "insights_created": 0}

    memories = result.data or []
    if len(memories) < 5:
        return {"user_id": user_id, "processed": 0, "insights_created": 0}

    # Build memory list for LLM
    mem_lines = []
    for i, m in enumerate(memories):
        # P0 Fix: Truncate value to prevent context_length_exceeded on long-session datasets (LoCoMo)
        val = str(m.get('value', ''))
        if len(val) > 3000:
            val = val[:3000] + "... (truncated for consolidation)"
        mem_lines.append(f"[{i}] ({m['category']}) {m['key']}: {val}")

    prompt = "以下是用户的记忆条目，请分析并找出跨记忆的模式：\n\n" + "\n".join(mem_lines)
    system = (
        "你是记忆整合专家。分析用户的多条记忆，发现跨记忆的模式、总结和矛盾。\n"
        "特别注意发现因果关系(causal)：如果A导致了B、A使B成为可能、A阻止了B，\n"
        "请在connections中明确标注relation为causal。因果关系是最有价值的洞察类型。\n\n"
        "请返回 JSON 数组，每个元素包含：\n"
        '- "insight_type": "pattern"（规律模式）/ "summary"（综合总结）/ "contradiction"（矛盾冲突）\n'
        '- "title": 简短标题（10字以内）\n'
        '- "content": 详细的洞察内容（1-3句话）\n'
        '- "importance": 0.0-1.0 重要性评分\n'
        '- "source_indices": 来源记忆的索引号数组，如 [0, 2, 5]\n'
        '- "connections": 记忆之间的关系数组，如 [{"from": 0, "to": 2, "relation": "supplements"}]\n'
        '  relation 可选值: same_customer, same_project, causal, contradicts, supplements\n'
        '  优先标注 causal（因果）关系\n\n'
        "只返回 JSON 数组。最多生成 5 条洞察。如果没有有意义的模式，返回 []。"
    )

    try:
        result_text = await AIService.call_llm(prompt, system)
    except Exception as e:
        logger.warning(f"Consolidation LLM call failed: {e}")
        return {"user_id": user_id, "processed": len(memories), "insights_created": 0}

    # Parse LLM response (using shared utility)
    parsed = parse_llm_json(result_text)
    if isinstance(parsed, list):
        insights = parsed
    else:
        logger.warning("Failed to parse consolidation LLM response")
        insights = []

    created = 0
    for insight in insights[:5]:
        try:
            # Map source indices to actual memory IDs
            source_indices = insight.get("source_indices", [])
            source_ids = [
                str(memories[i]["id"])
                for i in source_indices
                if isinstance(i, int) and 0 <= i < len(memories)
            ]
            if not source_ids:
                continue

            title = insight.get("title", "")[:100]
            content = insight.get("content", "")
            if not title or not content:
                continue

            # Generate embedding for the insight
            from app.services.vector_service import vector_service
            embedding = await vector_service.embed_text(f"{title}: {content}")

            # Insert into memory_consolidations
            await client.table("memory_consolidations").insert({
                "user_id": user_id,
                "organization_id": org_id,
                "insight_type": insight.get("insight_type", "pattern"),
                "title": title,
                "content": content,
                "source_memory_ids": source_ids,
                "importance": float(insight.get("importance", 0.6)),
                "embedding": embedding,
            }).execute()
            created += 1

            # Build connections between source memories (Feature 3)
            connections = insight.get("connections", [])
            await _write_connections(memories, connections, client)

        except Exception as e:
            logger.debug(f"Failed to store consolidation insight: {e}")

    # Mark all processed memories as consolidated
    if memories:
        mem_ids = [m["id"] for m in memories]
        try:
            await (
                client.table("conversation_memories")
                .update({"is_consolidated": True})
                .in_("id", mem_ids)
                .execute()
            )
        except Exception as e:
            logger.warning(f"Failed to mark memories as consolidated: {e}")

    if created:
        logger.info(
            f"Consolidation for user {user_id}: processed={len(memories)}, insights={created}"
        )

    return {"user_id": user_id, "processed": len(memories), "insights_created": created}


async def _write_connections(
    memories: list[dict],
    connections: list[dict],
    client: Any,
) -> None:
    """Write bidirectional connections between memories from LLM analysis."""
    for conn in connections:
        try:
            from_idx = conn.get("from")
            to_idx = conn.get("to")
            relation = conn.get("relation", "supplements")
            if not isinstance(from_idx, int) or not isinstance(to_idx, int):
                continue
            if from_idx < 0 or from_idx >= len(memories) or to_idx < 0 or to_idx >= len(memories):
                continue
            if from_idx == to_idx:
                continue

            from_id = str(memories[from_idx]["id"])
            to_id = str(memories[to_idx]["id"])
            strength = float(conn.get("strength", 0.7))

            # Write bidirectional: from->to and to->from
            for src_id, tgt_id in [(from_id, to_id), (to_id, from_id)]:
                # Read current connections
                res = (
                    await client.table("conversation_memories")
                    .select("connections")
                    .eq("id", src_id)
                    .maybe_single()
                    .execute()
                )
                current = (res.data or {}).get("connections", []) if res and res.data else []
                if not isinstance(current, list):
                    current = []
                # Avoid duplicates
                if any(c.get("memory_id") == tgt_id for c in current):
                    continue
                current.append({
                    "memory_id": tgt_id,
                    "relation": relation,
                    "strength": strength,
                })
                await (
                    client.table("conversation_memories")
                    .update({"connections": current})
                    .eq("id", src_id)
                    .execute()
                )
        except Exception as e:
            logger.debug(f"Failed to write memory connection: {e}")


async def generate_user_observation(
    user_id: str,
    org_id: str | None = None,
    db: Any = None,
) -> dict | None:
    """Generate a condensed user profile observation from top memories.

    Pulls the top-30 highest-importance memories and asks LLM to produce a
    concise user profile summary (3-8 sentences). Upserts the result into
    memory_consolidations with insight_type='observation'.

    Throttle: caller should skip if last observation was generated < 1 hour ago.

    Returns the observation record dict, or None on failure.
    """
    from app.services.ai_service import AIService

    client = db or supabase
    if not client:
        return None

    try:
        # Pull top-30 high-importance memories for this user
        result = await (
            client.table("conversation_memories")
            .select("id, category, key, value, importance")
            .eq("user_id", user_id)
            .is_("superseded_by", "null")
            .order("importance", desc=True)
            .limit(30)
            .execute()
        )
        memories = result.data or []
        if len(memories) < 3:
            return None

        mem_lines = []
        for m in memories:
            val = str(m.get('value', ''))
            if len(val) > 2000:
                val = val[:2000] + "..."
            mem_lines.append(f"- ({m['category']}) {m['key']}: {val}")

        prompt = "以下是某用户的关键记忆条目，请生成一份浓缩的用户画像摘要：\n\n" + "\n".join(mem_lines)
        system = (
            "你是用户画像分析专家。根据用户的记忆条目，生成一份简洁的用户画像摘要。\n"
            "要求：\n"
            "- 3-8句话，涵盖用户的核心偏好、习惯、重要关系和关键事实\n"
            '- 使用第三人称描述（如"该用户..."）\n'
            "- 优先提取高重要性的偏好和事实\n"
            "- 不要重复或罗列原始记忆，而是综合提炼\n"
            "- 直接输出摘要文本，不要添加标题或格式标记"
        )

        observation_text = await AIService.call_llm(prompt, system)
        if not observation_text or len(observation_text.strip()) < 10:
            return None

        observation_text = observation_text.strip()

        # Generate embedding
        from app.services.vector_service import vector_service
        embedding = await vector_service.embed_text(f"用户画像: {observation_text[:200]}")

        # Upsert: delete existing observation for this user, then insert new one
        try:
            await (
                client.table("memory_consolidations")
                .delete()
                .eq("user_id", user_id)
                .eq("insight_type", "observation")
                .execute()
            )
        except Exception:
            pass  # Table may not have existing observations

        row = {
            "user_id": user_id,
            "insight_type": "observation",
            "title": "用户画像摘要",
            "content": observation_text,
            "importance": 0.9,
            "source_memory_ids": [str(m["id"]) for m in memories[:10]],
        }
        if org_id:
            row["organization_id"] = org_id
        if embedding:
            row["embedding"] = embedding

        insert_result = await client.table("memory_consolidations").insert(row).execute()
        if insert_result.data:
            logger.info(f"[Observation] Generated user observation for {user_id}")
            return insert_result.data[0]

    except Exception as e:
        logger.warning(f"[Observation] Failed to generate observation for {user_id}: {e}")

    return None
