"""Memory CRUD operations: save, delete, clear."""

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.database import supabase

from .embedding import generate_embedding

logger = logging.getLogger(__name__)


async def save_memory(
    user_id: str,
    key: str,
    value: str,
    category: str = "preference",
    metadata: dict | None = None,
    importance: float = 0.5,
    org_id: str | None = None,
    db: Any = None,
) -> dict:
    """保存用户记忆条目（upsert by user_id + key），同时生成 embedding 向量"""
    client = db or supabase
    if not client:
        raise RuntimeError("数据库连接不可用")

    now = datetime.now(UTC).isoformat()

    # Generate embedding for semantic search
    embedding = await generate_embedding(f"{key}: {value}", org_id)

    # Check if key already exists for this user (latest version only)
    existing = (
        await client.table("conversation_memories")
        .select("id, access_count, version")
        .eq("user_id", user_id)
        .eq("key", key)
        .is_("superseded_by", "null")
        .maybe_single()
        .execute()
    )

    old_version = 0
    old_id = None
    if existing and existing.data:
        old_version = existing.data.get("version", 1)
        old_id = existing.data["id"]

    # Always insert a new record (append-only versioning)
    insert_data = {
        "user_id": user_id,
        "organization_id": org_id,
        "category": category,
        "key": key,
        "value": value,
        "metadata": metadata or {},
        "importance": importance,
        "version": old_version + 1,
        "access_count": 0,
        "last_accessed_at": now,
        "created_at": now,
        "updated_at": now,
    }
    if embedding:
        insert_data["embedding"] = embedding
    try:
        result = await client.table("conversation_memories").insert(insert_data).execute()
    except Exception as insert_err:
        err_str = str(insert_err)
        if embedding and ("embedding" in err_str or "PGRST204" in err_str):
            logger.warning("embedding column not found, saving without embedding")
            insert_data.pop("embedding", None)
            result = await client.table("conversation_memories").insert(insert_data).execute()
        elif "version" in err_str or "superseded_by" in err_str:
            # Columns not yet migrated — fall back to legacy upsert
            logger.warning("version/superseded_by columns missing, falling back to legacy upsert")
            insert_data.pop("version", None)
            insert_data.pop("superseded_by", None)
            if old_id:
                update_data = {k: v for k, v in insert_data.items() if k not in ("user_id", "organization_id", "key", "created_at", "access_count", "last_accessed_at")}
                result = await client.table("conversation_memories").update(update_data).eq("id", old_id).execute()
            else:
                result = await client.table("conversation_memories").insert(insert_data).execute()
        else:
            raise

    # Mark old version as superseded
    if old_id and result.data:
        new_record = result.data[0] if isinstance(result.data, list) else result.data
        new_id = new_record.get("id")
        if new_id and new_id != old_id:
            try:
                await (
                    client.table("conversation_memories")
                    .update({"superseded_by": new_id})
                    .eq("id", old_id)
                    .execute()
                )
            except Exception:
                logger.debug(f"Failed to mark old version {old_id} as superseded (column may not exist)")

    if not result.data:
        raise RuntimeError("保存记忆失败")

    saved = result.data[0] if isinstance(result.data, list) else result.data
    logger.info(f"Saved memory for user {user_id}: key={key}, category={category}")
    return saved


async def delete_memory(
    user_id: str,
    memory_id: str,
    db: Any = None,
) -> bool:
    """删除单条记忆"""
    client = db or supabase
    if not client:
        return False

    result = (
        await client.table("conversation_memories").delete().eq("id", memory_id).eq("user_id", user_id).execute()
    )

    deleted = bool(result.data)
    if deleted:
        logger.info(f"Deleted memory {memory_id} for user {user_id}")
    return deleted


async def clear_memories(
    user_id: str,
    category: str | None = None,
    db: Any = None,
) -> int:
    """清除记忆（可按分类清除）"""
    client = db or supabase
    if not client:
        return 0

    query = client.table("conversation_memories").delete().eq("user_id", user_id)

    if category:
        query = query.eq("category", category)

    result = await query.execute()
    count = len(result.data) if result.data else 0

    logger.info(f"Cleared {count} memories for user {user_id}{f' (category={category})' if category else ''}")
    return count


async def get_memory_history(
    user_id: str,
    key: str,
    limit: int = 10,
    db: Any = None,
) -> list[dict]:
    """获取某个 key 的所有历史版本（按版本号倒序）"""
    client = db or supabase
    if not client:
        return []

    try:
        result = (
            await client.table("conversation_memories")
            .select("id, key, value, category, version, importance, created_at, updated_at")
            .eq("user_id", user_id)
            .eq("key", key)
            .order("version", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.debug(f"get_memory_history failed (columns may not exist): {e}")
        return []
