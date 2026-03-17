"""Memory conflict resolution — LLM-driven ADD/UPDATE/DELETE/NONE decisions.

Inspired by Mem0's approach: when new memories are extracted, they are
compared against existing semantically similar memories. An LLM decides
whether to ADD (new info), UPDATE (merge/replace), DELETE (contradiction),
or NONE (already exists).

This eliminates contradictory memories and keeps the memory store
clean and consistent.
"""

import logging
from typing import Any

from app.core.database import supabase

from .audit import log_memory_change
from .embedding import generate_embedding
from .llm_utils import parse_llm_json, prepare_memories_for_llm, restore_real_ids

logger = logging.getLogger(__name__)

# ── Conflict resolution prompt (inspired by Mem0's DEFAULT_UPDATE_MEMORY_PROMPT) ──

CONFLICT_RESOLUTION_PROMPT = """你是一个智能记忆管理器，负责管理用户的记忆库。
你可以执行四种操作：(1) 添加新记忆, (2) 更新已有记忆, (3) 删除已有记忆, (4) 无需操作。

对比新提取的信息与已有记忆，对每条新信息决定：
- ADD: 全新的信息，记忆库中没有相关内容
- UPDATE: 已有相关记忆但新信息更完整/更新/需要合并
- DELETE: 新信息与已有记忆矛盾（如旧="喜欢芝士" ← 新="讨厌芝士"）
- NONE: 新信息与已有记忆语义相同，无需变更

判断规则：
1. ADD — 旧记忆中完全没有相关的新信息
2. UPDATE — 同一主题但信息发生变化:
   - 旧="喜欢打球" + 新="喜欢和朋友打球" → UPDATE（信息更完整）
   - 旧="负责华东区" + 新="负责华东区和华南区" → UPDATE（范围扩大）
   - 合并时保留所有有价值的信息
3. DELETE — 新信息直接否定/矛盾旧信息:
   - 旧="喜欢芝士" + 新="讨厌芝士" → DELETE 旧的
4. NONE — 语义完全相同:
   - 旧="喜欢芝士披萨" == 新="爱芝士披萨" → NONE"""

CONFLICT_RESOLUTION_USER_TEMPLATE = """{system_prompt}

已有记忆：
```
{existing_memories}
```

新提取的信息：
```
{new_facts}
```

请严格以如下 JSON 格式返回决策结果：

{{
    "memory": [
        {{
            "id": "<已有记忆的 ID (UPDATE/DELETE/NONE) 或 'new' (ADD)>",
            "text": "<最终的记忆内容>",
            "event": "<ADD / UPDATE / DELETE / NONE>",
            "old_memory": "<仅 UPDATE 时需要：被更新的旧记忆内容>"
        }}
    ]
}}

只返回 JSON，不要其他文字。"""


async def resolve_memory_conflicts(
    user_id: str,
    new_memories: list[dict],
    org_id: str | None = None,
    db: Any = None,
) -> list[dict]:
    """对新提取的记忆执行冲突解决，返回处理结果列表。

    流程:
    1. 对每条新记忆，向量搜索 top-5 相似旧记忆
    2. 如无相似旧记忆 → 直接 ADD
    3. 有相似旧记忆 → LLM 批量判断 ADD/UPDATE/DELETE/NONE
    4. 执行对应的数据库操作 + 记录审计日志

    Args:
        user_id: 用户 ID
        new_memories: 新提取的记忆列表 [{key, value, category, importance, ...}]
        org_id: 组织 ID (用于 embedding 模型选择)
        db: 数据库客户端

    Returns:
        处理结果列表 [{id, event, text, ...}]
    """
    from .storage import save_memory as _save_memory

    client = db or supabase
    if not client or not new_memories:
        return []

    results: list[dict] = []

    # Collect all new facts and search for similar existing memories
    all_similar: list[dict] = []
    new_facts_text: list[str] = []

    for mem in new_memories:
        value = mem.get("value", "")
        if not value:
            continue
        new_facts_text.append(value)

        # Search for similar existing memories
        try:
            similar = await _search_similar(user_id, value, org_id=org_id, db=client)
            for s in similar:
                if not any(existing["id"] == s["id"] for existing in all_similar):
                    all_similar.append(s)
        except Exception as e:
            logger.debug(f"Similar memory search failed: {e}")

    # Fast path: no similar memories → all are ADDs, use standard save
    if not all_similar:
        for mem in new_memories:
            try:
                saved = await _save_memory(
                    user_id=user_id,
                    key=mem["key"],
                    value=mem["value"],
                    category=mem.get("category", "preference"),
                    importance=mem.get("importance", 0.5),
                    org_id=org_id,
                    db=client,
                    enriched_value=mem.get("enriched_value"),
                    valid_from=mem.get("valid_from"),
                )
                results.append({"id": saved.get("id"), "event": "ADD", "text": mem["value"]})
                # Audit log
                await log_memory_change(
                    memory_id=str(saved.get("id", "")),
                    user_id=user_id,
                    action="ADD",
                    new_value=mem["value"],
                    actor="conflict_resolution",
                    db=client,
                )
            except Exception as e:
                logger.warning(f"Failed to save new memory: {e}")
        return results

    # Slow path: have similar memories → LLM decides the action
    try:
        actions = await _llm_resolve(all_similar, new_facts_text)
    except Exception as e:
        logger.warning(f"LLM conflict resolution failed, falling back to ADD-all: {e}")
        # Fallback: save all as new memories without conflict resolution
        for mem in new_memories:
            try:
                saved = await _save_memory(
                    user_id=user_id,
                    key=mem["key"],
                    value=mem["value"],
                    category=mem.get("category", "preference"),
                    importance=mem.get("importance", 0.5),
                    org_id=org_id,
                    db=client,
                    enriched_value=mem.get("enriched_value"),
                    valid_from=mem.get("valid_from"),
                )
                results.append({"id": saved.get("id"), "event": "ADD", "text": mem["value"]})
            except Exception as e2:
                logger.warning(f"Fallback save failed: {e2}")
        return results

    # Execute the LLM-decided actions
    for action in actions:
        event = action.get("event", "NONE")
        text = action.get("text", "")
        action_id = action.get("id", "")

        if not text and event != "DELETE":
            continue

        try:
            if event == "ADD":
                # Find the matching new memory entry for key/category info
                matching_new = _find_matching_new_mem(text, new_memories)
                saved = await _save_memory(
                    user_id=user_id,
                    key=matching_new.get("key", f"resolved_{hash(text) % 10000:04d}"),
                    value=text,
                    category=matching_new.get("category", "preference"),
                    importance=matching_new.get("importance", 0.5),
                    org_id=org_id,
                    db=client,
                    enriched_value=matching_new.get("enriched_value"),
                    valid_from=matching_new.get("valid_from"),
                )
                results.append({"id": saved.get("id"), "event": "ADD", "text": text})
                await log_memory_change(
                    memory_id=str(saved.get("id", "")),
                    user_id=user_id,
                    action="ADD",
                    new_value=text,
                    actor="conflict_resolution",
                    db=client,
                )

            elif event == "UPDATE" and action_id:
                old_memory_text = action.get("old_memory", "")
                await _update_existing_memory(
                    memory_id=action_id,
                    new_value=text,
                    user_id=user_id,
                    db=client,
                )
                results.append({
                    "id": action_id,
                    "event": "UPDATE",
                    "text": text,
                    "previous_memory": old_memory_text,
                })
                await log_memory_change(
                    memory_id=action_id,
                    user_id=user_id,
                    action="UPDATE",
                    old_value=old_memory_text,
                    new_value=text,
                    reason="LLM conflict resolution: merged or replaced with newer info",
                    actor="conflict_resolution",
                    db=client,
                )

            elif event == "DELETE" and action_id:
                await _delete_existing_memory(
                    memory_id=action_id,
                    user_id=user_id,
                    db=client,
                )
                results.append({"id": action_id, "event": "DELETE", "text": text})
                await log_memory_change(
                    memory_id=action_id,
                    user_id=user_id,
                    action="DELETE",
                    old_value=text,
                    reason="LLM conflict resolution: contradicted by new information",
                    actor="conflict_resolution",
                    db=client,
                )

            # NONE: no action needed

        except Exception as e:
            logger.warning(f"Failed to execute memory action {event}: {e}")

    if results:
        event_summary = {}
        for r in results:
            evt = r.get("event", "UNKNOWN")
            event_summary[evt] = event_summary.get(evt, 0) + 1
        logger.info(f"[ConflictResolve] user={user_id} results: {event_summary}")

    return results


# ── Internal helpers ──────────────────────────────────────────────


async def _search_similar(
    user_id: str,
    query: str,
    limit: int = 5,
    org_id: str | None = None,
    db: Any = None,
) -> list[dict]:
    """Search for semantically similar existing memories."""
    client = db or supabase
    if not client:
        return []

    embedding = await generate_embedding(query, org_id)
    if not embedding:
        return []

    try:
        result = await client.rpc(
            "match_memories",
            {
                "query_embedding": embedding,
                "match_count": limit,
                "filter_user_id": user_id,
            },
        ).execute()
        return result.data or []
    except Exception:
        # Fallback: keyword search if RPC not available
        try:
            result = (
                await client.table("conversation_memories")
                .select("id, key, value, category, importance")
                .eq("user_id", user_id)
                .is_("superseded_by", "null")
                .ilike("value", f"%{query[:50]}%")
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception as e2:
            logger.debug(f"Keyword fallback search also failed: {e2}")
            return []


async def _llm_resolve(
    existing_memories: list[dict],
    new_facts: list[str],
) -> list[dict]:
    """Call LLM to decide ADD/UPDATE/DELETE/NONE for each new fact."""
    from app.services.ai_service import AIService

    # Use integer ID mapping to prevent hallucination
    safe_memories, id_mapping = prepare_memories_for_llm(existing_memories)

    prompt = CONFLICT_RESOLUTION_USER_TEMPLATE.format(
        system_prompt=CONFLICT_RESOLUTION_PROMPT,
        existing_memories=safe_memories,
        new_facts=new_facts,
    )

    response_text = await AIService.call_llm(
        prompt,
        "你是智能记忆管理器。只返回JSON。",
    )

    parsed = parse_llm_json(response_text)
    if not parsed or not isinstance(parsed, dict):
        logger.warning("LLM conflict resolution returned unparseable response")
        return []

    # Restore real IDs
    parsed = restore_real_ids(parsed, id_mapping)

    actions = parsed.get("memory", [])
    if not isinstance(actions, list):
        return []

    # Filter valid actions only
    valid_actions = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        event = action.get("event", "")
        if event not in ("ADD", "UPDATE", "DELETE", "NONE"):
            continue
        valid_actions.append(action)

    return valid_actions


async def _update_existing_memory(
    memory_id: str,
    new_value: str,
    user_id: str,
    db: Any = None,
) -> str | None:
    """Soft-expire the old memory and INSERT a new version.

    Instead of overwriting, this preserves the history chain:
    old record gets superseded_by → new record, keeping the full timeline.
    Returns the new memory ID if created, None otherwise.
    """
    from datetime import UTC, datetime

    client = db or supabase
    if not client:
        return None

    # 1. Read the old memory to clone its metadata
    try:
        old_result = (
            await client.table("conversation_memories")
            .select("user_id, organization_id, category, key, importance, version, metadata")
            .eq("id", memory_id)
            .maybe_single()
            .execute()
        )
        old = old_result.data if old_result else None
    except Exception:
        old = None

    # 2. Generate embedding for the new value
    embedding = await generate_embedding(new_value)

    now_iso = datetime.now(UTC).isoformat()
    new_version = (old.get("version", 1) + 1) if old else 2

    # 3. INSERT new version
    insert_data: dict[str, Any] = {
        "user_id": user_id,
        "organization_id": old.get("organization_id") if old else None,
        "category": old.get("category", "general") if old else "general",
        "key": old.get("key", "") if old else "",
        "value": new_value,
        "importance": old.get("importance", 0.5) if old else 0.5,
        "version": new_version,
        "metadata": old.get("metadata") if old else None,
        "valid_from": now_iso,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    if embedding:
        insert_data["embedding"] = embedding

    new_id = None
    try:
        new_result = await client.table("conversation_memories").insert(insert_data).execute()
        if new_result.data:
            row = new_result.data[0] if isinstance(new_result.data, list) else new_result.data
            new_id = row.get("id")
    except Exception as e:
        logger.warning(f"[ConflictRes] Failed to insert new memory version: {e}")
        # Fallback: in-place update if INSERT fails (e.g., column not yet migrated)
        update_data: dict[str, Any] = {"value": new_value, "updated_at": now_iso}
        if embedding:
            update_data["embedding"] = embedding
        await (
            client.table("conversation_memories")
            .update(update_data)
            .eq("id", memory_id)
            .eq("user_id", user_id)
            .execute()
        )
        return None

    # 4. Soft-expire old record: set superseded_by → new ID
    if new_id:
        try:
            await (
                client.table("conversation_memories")
                .update({"superseded_by": new_id, "updated_at": now_iso})
                .eq("id", memory_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as e:
            logger.warning(f"[ConflictRes] Failed to soft-expire old memory: {e}")

    return new_id


async def _delete_existing_memory(
    memory_id: str,
    user_id: str,
    db: Any = None,
) -> None:
    """Delete an existing memory by ID."""
    client = db or supabase
    if not client:
        return

    await (
        client.table("conversation_memories")
        .delete()
        .eq("id", memory_id)
        .eq("user_id", user_id)
        .execute()
    )


def _find_matching_new_mem(text: str, new_memories: list[dict]) -> dict:
    """Find the new memory entry that best matches the given text."""
    best_match = {}
    best_overlap = 0

    for mem in new_memories:
        value = mem.get("value", "")
        # Simple overlap score: number of common characters
        overlap = len(set(text) & set(value))
        if overlap > best_overlap:
            best_overlap = overlap
            best_match = mem

    return best_match or (new_memories[0] if new_memories else {})
