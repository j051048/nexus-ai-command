"""Memory CRUD operations: save, delete, clear."""

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.database import supabase

from .embedding import generate_embedding
from .pii_filter import sanitize_pii

logger = logging.getLogger(__name__)

# Categories whose value field is encrypted at rest
_ENCRYPTED_CATEGORIES = frozenset({"explicit_memory", "personal_info", "episodic"})


def _encrypt_value(value: str, category: str) -> str:
    """Encrypt value for sensitive categories, passthrough for others."""
    if category not in _ENCRYPTED_CATEGORIES or not value:
        return value
    try:
        from app.services.encryption_service import encryption_service
        return encryption_service.encrypt(value)
    except Exception as e:
        logger.warning(f"Memory encryption failed (storing plaintext): {e}")
        return value


def decrypt_memory_value(value: str) -> str:
    """Decrypt a memory value if it's Fernet-encrypted, otherwise return as-is."""
    if not value:
        return value
    try:
        from app.services.encryption_service import EncryptionService
        if EncryptionService.is_encrypted(value):
            return EncryptionService.decrypt(value)
    except Exception as e:
        logger.warning(f"Memory decryption failed (returning raw): {e}")
    return value


async def save_memory(
    user_id: str,
    key: str,
    value: str,
    category: str = "preference",
    metadata: dict | None = None,
    importance: float = 0.5,
    org_id: str | None = None,
    db: Any = None,
    enriched_value: str | None = None,
    valid_from: str | None = None,
    pattern_key: str | None = None,
    *,
    source: str | None = None,
    extraction_method: str | None = None,
    fact_type: str = "fact",
    confidence: float = 1.0,
    valid_until: str | None = None,
) -> dict:
    """保存用户记忆条目（upsert by user_id + key），同时生成 embedding 向量"""
    client = db or supabase
    if not client:
        raise RuntimeError("数据库连接不可用")

    now = datetime.now(UTC).isoformat()

    # P0 LoCoMo Fix: Normalize temporal context before storage
    from .temporal_normalizer import normalize_temporal_context
    metadata = normalize_temporal_context(
        session_date=valid_from or now,
        text=value,
        metadata=metadata
    )

    # PII sanitization — mask sensitive data before persisting
    value = sanitize_pii(value)
    if enriched_value:
        enriched_value = sanitize_pii(enriched_value)

    # Generate embedding for semantic search (prefer enriched_value for better semantics)
    # Hindsight-inspired: inject date prefix into embedding text for temporal awareness
    embed_text = enriched_value or f"{key}: {value}"
    if valid_from:
        try:
            from datetime import datetime as _dt
            _vf = _dt.fromisoformat(str(valid_from).replace("Z", "+00:00"))
            embed_text = f"[Date: {_vf.strftime('%Y-%m-%d')} / {_vf.strftime('%d %B %Y')}] {embed_text}"
        except (ValueError, TypeError):
            pass
    embedding = await generate_embedding(embed_text, org_id)

    # Encrypt sensitive categories at rest (AFTER embedding, which needs plaintext)
    value = _encrypt_value(value, category)
    if enriched_value:
        enriched_value = _encrypt_value(enriched_value, category)

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

    # Semantic dedup: if no exact key match, check for semantically similar memories
    if not old_id and embedding:
        try:
            similar = await _find_semantically_similar(
                user_id, embedding, threshold=0.92, category=category, db=client
            )
            if similar:
                # Found a semantically similar memory — merge into it
                old_id = similar["id"]
                old_version = similar.get("version", 1)
                key = similar.get("key", key)  # reuse existing key for version chain
                logger.info(
                    f"Semantic dedup: merging '{key}' with similar memory "
                    f"(id={old_id}, similarity≥0.92)"
                )
        except Exception:
            logger.debug("Semantic dedup check failed, proceeding with normal insert", exc_info=True)

    # P0 Fix: Per-user memory limit (500) — evict lowest-importance when full
    if not old_id:
        await _enforce_memory_limit(user_id, client, max_memories=5000)

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
    if enriched_value:
        insert_data["enriched_value"] = enriched_value
    if valid_from:
        insert_data["valid_from"] = valid_from
    if pattern_key:
        insert_data["pattern_key"] = pattern_key
        insert_data["first_seen_at"] = now
        insert_data["recurrence_count"] = 1
    if fact_type and fact_type != "fact":
        insert_data["fact_type"] = fact_type
    if confidence != 1.0:
        insert_data["confidence"] = confidence
    if valid_until:
        insert_data["valid_until"] = valid_until
    try:
        result = await client.table("conversation_memories").insert(insert_data).execute()
    except Exception as insert_err:
        err_str = str(insert_err)
        if "enriched_value" in err_str or "valid_from" in err_str:
            logger.warning("enriched_value/valid_from columns not found, saving without them")
            insert_data.pop("enriched_value", None)
            insert_data.pop("valid_from", None)
            try:
                result = await client.table("conversation_memories").insert(insert_data).execute()
            except Exception as retry_err:
                err_str = str(retry_err)
                if embedding and ("embedding" in err_str or "PGRST204" in err_str):
                    insert_data.pop("embedding", None)
                    result = await client.table("conversation_memories").insert(insert_data).execute()
                else:
                    raise retry_err
        elif embedding and ("embedding" in err_str or "PGRST204" in err_str):
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

    # Non-fatal audit logging
    try:
        from .audit import log_memory_change
        if old_id:
            await log_memory_change(
                memory_id=str(saved.get("id", "")),
                user_id=user_id,
                action="UPDATE",
                old_value=None,  # old value not readily available here
                new_value=value,
                reason="Version update via save_memory",
                actor="system",
                db=client,
                source=source,
                extraction_method=extraction_method,
            )
        else:
            await log_memory_change(
                memory_id=str(saved.get("id", "")),
                user_id=user_id,
                action="ADD",
                new_value=value,
                actor="system",
                db=client,
                source=source,
                extraction_method=extraction_method,
            )
    except Exception:
        pass  # audit is non-fatal

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

    # Fetch value before deletion for audit trail
    old_value = None
    try:
        existing = (
            await client.table("conversation_memories")
            .select("value")
            .eq("id", memory_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if existing and existing.data:
            old_value = existing.data.get("value")
    except Exception:
        pass

    result = (
        await client.table("conversation_memories").delete().eq("id", memory_id).eq("user_id", user_id).execute()
    )

    deleted = bool(result.data)
    if deleted:
        logger.info(f"Deleted memory {memory_id} for user {user_id}")
        # Non-fatal audit logging
        try:
            from .audit import log_memory_change
            await log_memory_change(
                memory_id=memory_id,
                user_id=user_id,
                action="DELETE",
                old_value=old_value,
                reason="User-initiated deletion",
                actor="user_explicit",
                db=client,
            )
        except Exception:
            pass  # audit is non-fatal
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


async def _find_semantically_similar(
    user_id: str,
    embedding: list[float],
    threshold: float = 0.92,
    category: str | None = None,
    db: Any = None,
) -> dict | None:
    """Find the most similar active memory via pgvector cosine search.

    Returns the top-1 match above `threshold`, or None.
    Uses the existing search_memories_by_embedding RPC.
    """
    client = db or supabase
    if not client:
        return None

    params: dict[str, Any] = {
        "match_user_id": user_id,
        "query_embedding": embedding,
        "match_limit": 1,
    }

    try:
        result = await client.rpc("search_memories_by_embedding", params).execute()
        if result.data and len(result.data) > 0:
            match = result.data[0]
            # Check similarity threshold (RPC returns similarity field)
            if match.get("similarity", 0) < threshold:
                return None
            # Filter by category if specified (RPC may not support this natively)
            if category and match.get("category") and match["category"] != category:
                return None
            return match
    except Exception as e:
        logger.debug(f"_find_semantically_similar RPC failed: {e}")

    return None


async def _enforce_memory_limit(
    user_id: str, db: Any, *, max_memories: int = 500
) -> None:
    """Evict lowest-importance memories when a user exceeds the cap.

    Deletes the bottom 10% by importance to avoid evicting on every single insert.
    Protected categories (explicit_memory, policy) are never evicted.
    """
    try:
        count_res = (
            await db.table("conversation_memories")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .is_("superseded_by", "null")
            .execute()
        )
        total = count_res.count if hasattr(count_res, "count") and count_res.count is not None else len(count_res.data or [])
        if total < max_memories:
            return

        # Evict bottom 10% (at least 1) ordered by importance ASC
        evict_count = max(int(max_memories * 0.1), 1)
        victims = (
            await db.table("conversation_memories")
            .select("id")
            .eq("user_id", user_id)
            .is_("superseded_by", "null")
            .not_.in_("category", ["explicit_memory", "policy"])
            .order("importance", desc=False)
            .limit(evict_count)
            .execute()
        )
        if victims.data:
            victim_ids = [v["id"] for v in victims.data]
            await (
                db.table("conversation_memories")
                .delete()
                .in_("id", victim_ids)
                .execute()
            )
            logger.info(
                "[MemoryLimit] Evicted %d low-importance memories for user %s (total was %d, cap %d)",
                len(victim_ids), user_id, total, max_memories,
            )
    except Exception as e:
        logger.debug("[MemoryLimit] Limit enforcement failed (non-fatal): %s", e)
