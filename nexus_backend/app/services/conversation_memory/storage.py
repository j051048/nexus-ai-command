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

    # Check if key already exists for this user
    existing = (
        await client.table("conversation_memories")
        .select("id, access_count")
        .eq("user_id", user_id)
        .eq("key", key)
        .maybe_single()
        .execute()
    )

    update_data = {
        "value": value,
        "category": category,
        "metadata": metadata or {},
        "importance": importance,
        "updated_at": now,
    }
    if embedding:
        update_data["embedding"] = embedding

    if existing and existing.data:
        # Update existing memory
        try:
            result = (
                await client.table("conversation_memories")
                .update(update_data)
                .eq("id", existing.data["id"])
                .execute()
            )
        except Exception as update_err:
            err_str = str(update_err)
            if embedding and ("embedding" in err_str or "PGRST204" in err_str):
                logger.warning("embedding column not found in schema cache, updating without embedding")
                update_data.pop("embedding", None)
                result = (
                    await client.table("conversation_memories")
                    .update(update_data)
                    .eq("id", existing.data["id"])
                    .execute()
                )
            else:
                raise
    else:
        # Insert new memory
        insert_data = {
            "user_id": user_id,
            "organization_id": org_id,
            "category": category,
            "key": key,
            "value": value,
            "metadata": metadata or {},
            "importance": importance,
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
            # Fallback: if embedding column doesn't exist (PGRST204), retry without it
            err_str = str(insert_err)
            if embedding and ("embedding" in err_str or "PGRST204" in err_str):
                logger.warning("embedding column not found in schema cache, saving without embedding")
                insert_data.pop("embedding", None)
                result = await client.table("conversation_memories").insert(insert_data).execute()
            else:
                raise

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
