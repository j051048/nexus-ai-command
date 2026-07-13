"""Memory CRUD operations: save, delete, clear."""

import logging
import os
from datetime import UTC, datetime
from typing import Any

from app.core.database import supabase

from .admission import evaluate_memory_admission
from .embedding import generate_embedding
from .pii_filter import sanitize_pii
from .visibility import determine_visibility

logger = logging.getLogger(__name__)

# Categories whose value field is encrypted at rest
_ENCRYPTED_CATEGORIES = frozenset(
    {
        "explicit_memory",
        "personal_info",
        "episodic",
        "tool_correction",
        "instrument_identity",
        "calibration_baseline",
        "maintenance_episode",
        "experiment_method",
        "compliance_evidence",
    }
)


class MemoryEncryptionError(RuntimeError):
    """Raised when a sensitive memory cannot be encrypted safely."""


def _encrypt_value(value: str, category: str) -> str:
    """Encrypt value for sensitive categories, passthrough for others."""
    if category not in _ENCRYPTED_CATEGORIES or not value:
        return value
    try:
        from app.services.encryption_service import encryption_service

        return encryption_service.encrypt(value)
    except Exception as e:
        logger.error(
            "Sensitive memory encryption failed; write rejected", exc_info=True
        )
        raise MemoryEncryptionError("Sensitive memory could not be encrypted") from e


def decrypt_memory_value(value: str) -> str:
    """Decrypt a memory value if it's Fernet-encrypted, otherwise return as-is."""
    if not value:
        return value
    try:
        from app.services.encryption_service import EncryptionService

        if EncryptionService.is_encrypted(value):
            return EncryptionService.decrypt(value)
    except Exception:
        logger.error("Memory decryption failed", exc_info=True)
        return "[记忆暂时无法解密]"
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
    visibility: str | None = None,
    lifecycle_state: str | None = None,
    sensitivity: str | None = None,
    expires_at: str | None = None,
    evidence_ref: str | None = None,
) -> dict:
    """保存用户记忆条目（upsert by user_id + key），同时生成 embedding 向量"""
    client = db or supabase
    if not client:
        raise RuntimeError("数据库连接不可用")

    now = datetime.now(UTC).isoformat()

    admission = evaluate_memory_admission(
        value=value,
        category=category,
        confidence=confidence,
        source=source,
        extraction_method=extraction_method,
        metadata=metadata,
        valid_until=valid_until,
        evidence_ref=evidence_ref,
    )
    if not admission.allowed:
        raise ValueError(f"Memory rejected by admission policy: {admission.reason}")
    lifecycle_state = lifecycle_state or admission.lifecycle_state
    sensitivity = sensitivity or admission.sensitivity
    expires_at = expires_at or admission.expires_at

    # Ensure org_id is set — RLS requires organization_id = get_user_org_id(auth.uid())
    if not org_id:
        try:
            from app.core.database import supabase as _supabase

            org_resp = (
                await _supabase.table("organization_members")
                .select("organization_id")
                .eq("user_id", user_id)
                .maybe_single()
                .execute()
            )
            if org_resp and org_resp.data:
                org_id = org_resp.data["organization_id"]
        except Exception:
            pass
    if not org_id:
        raise RuntimeError(f"Cannot save memory: no valid org_id for user {user_id}")

    # P0 LoCoMo Fix: Normalize temporal context before storage
    from .temporal_normalizer import normalize_temporal_context

    metadata = normalize_temporal_context(
        session_date=valid_from or now, text=value, metadata=metadata
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
    embedding_scope = os.getenv("MEMORY_EMBEDDING_SCOPE", "external").lower()
    sensitive_external_embedding = (
        sensitivity == "restricted" and embedding_scope == "external"
    )
    if embedding_scope == "disabled" or sensitive_external_embedding:
        embedding = None
        admission.provenance["embedding_policy"] = "skipped_sensitive_content"
    else:
        embedding = await generate_embedding(embed_text, org_id)

    # Encrypt sensitive categories at rest (AFTER embedding, which needs plaintext)
    value = _encrypt_value(value, category)
    if enriched_value:
        enriched_value = _encrypt_value(enriched_value, category)

    # Check if key already exists for this user (latest version only)
    existing = (
        await client.table("conversation_memories")
        .select("id, access_count, version, importance")
        .eq("user_id", user_id)
        .eq("key", key)
        .is_("superseded_by", "null")
        .maybe_single()
        .execute()
    )

    old_version = 0
    old_id = None
    old_access_count = 0
    old_importance = importance
    if existing and existing.data:
        old_version = existing.data.get("version", 1)
        old_id = existing.data["id"]
        old_access_count = existing.data.get("access_count", 0)
        old_importance = existing.data.get("importance", importance)
        # P1 Fix: 动态调整重要性 - 经常访问的记忆提升重要性
        if old_access_count > 5:
            importance = min(old_importance + 0.05, 1.0)

    # G5 LoCoMo Skip: Heavy DB checks during bench
    is_bench = os.getenv("LOCOMO_INGEST_MODE") == "1"

    # Semantic dedup: if no exact key match, check for semantically similar memories
    if not old_id and embedding and not is_bench:
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
            logger.error(
                "Semantic dedup check failed, proceeding with normal insert",
                exc_info=True,
            )

    # P0 Fix: Per-user memory limit (500) — evict lowest-importance when full
    if not old_id and not is_bench:
        await _enforce_memory_limit(user_id, client, category=category)

    # P1.1: Auto-determine visibility level for RBAC
    resolved_visibility = determine_visibility(category, importance, visibility)

    # P2.1: Generate semantic tags for pre-filtering
    from .semantic_tags import generate_semantic_tags

    semantic_tags = generate_semantic_tags(category, key, value, fact_type=fact_type)

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
        "lifecycle_state": lifecycle_state,
        "sensitivity": sensitivity,
        "provenance": admission.provenance,
        "expires_at": expires_at,
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
    if evidence_ref:
        insert_data["evidence_ref"] = evidence_ref
    # P1.1: Visibility field (graceful — skip if column doesn't exist yet)
    if resolved_visibility != "private":
        insert_data["visibility"] = resolved_visibility
    # P2.1: Semantic tags (graceful — skip if column doesn't exist yet)
    if semantic_tags:
        insert_data["semantic_tags"] = semantic_tags
    result = None
    used_atomic_rpc = False
    if hasattr(client, "rpc"):
        rpc_params = {
            "p_user_id": user_id,
            "p_organization_id": org_id,
            "p_category": category,
            "p_key": key,
            "p_value": value,
            "p_metadata": metadata or {},
            "p_importance": importance,
            "p_embedding": embedding,
            "p_enriched_value": enriched_value,
            "p_valid_from": valid_from,
            "p_valid_until": valid_until,
            "p_pattern_key": pattern_key,
            "p_fact_type": fact_type,
            "p_confidence": confidence,
            "p_visibility": resolved_visibility,
            "p_semantic_tags": semantic_tags or [],
            "p_lifecycle_state": lifecycle_state,
            "p_sensitivity": sensitivity,
            "p_provenance": admission.provenance,
            "p_expires_at": expires_at,
            "p_evidence_ref": evidence_ref,
        }
        try:
            result = await client.rpc(
                "upsert_conversation_memory_version", rpc_params
            ).execute()
            used_atomic_rpc = True
        except Exception as rpc_error:
            error_text = str(rpc_error).lower()
            if not any(
                marker in error_text
                for marker in ("pgrst202", "42883", "function", "schema cache")
            ):
                raise
            logger.warning(
                "Atomic memory RPC is not available yet; using legacy write path"
            )

    try:
        if result is None:
            result = (
                await client.table("conversation_memories")
                .insert(insert_data)
                .execute()
            )
    except Exception as insert_err:
        err_str = str(insert_err)
        if "enriched_value" in err_str or "valid_from" in err_str:
            logger.warning(
                "enriched_value/valid_from columns not found, saving without them"
            )
            insert_data.pop("enriched_value", None)
            insert_data.pop("valid_from", None)
            try:
                result = (
                    await client.table("conversation_memories")
                    .insert(insert_data)
                    .execute()
                )
            except Exception as retry_err:
                err_str = str(retry_err)
                if embedding and ("embedding" in err_str or "PGRST204" in err_str):
                    insert_data.pop("embedding", None)
                    result = (
                        await client.table("conversation_memories")
                        .insert(insert_data)
                        .execute()
                    )
                else:
                    raise retry_err
        elif embedding and ("embedding" in err_str or "PGRST204" in err_str):
            logger.warning("embedding column not found, saving without embedding")
            insert_data.pop("embedding", None)
            result = (
                await client.table("conversation_memories")
                .insert(insert_data)
                .execute()
            )
        elif "version" in err_str or "superseded_by" in err_str:
            # Columns not yet migrated — fall back to legacy upsert
            logger.warning(
                "version/superseded_by columns missing, falling back to legacy upsert"
            )
            insert_data.pop("version", None)
            insert_data.pop("superseded_by", None)
            if old_id:
                update_data = {
                    k: v
                    for k, v in insert_data.items()
                    if k
                    not in (
                        "user_id",
                        "organization_id",
                        "key",
                        "created_at",
                        "access_count",
                        "last_accessed_at",
                    )
                }
                result = (
                    await client.table("conversation_memories")
                    .update(update_data)
                    .eq("id", old_id)
                    .execute()
                )
            else:
                result = (
                    await client.table("conversation_memories")
                    .insert(insert_data)
                    .execute()
                )
        else:
            raise

    # Mark old version as superseded
    if old_id and result.data and not used_atomic_rpc:
        new_record = result.data[0] if isinstance(result.data, list) else result.data
        new_id = new_record.get("id")
        if new_id and new_id != old_id:
            try:
                await client.table("conversation_memories").update(
                    {"superseded_by": new_id}
                ).eq("id", old_id).execute()
            except Exception:
                logger.error(
                    f"Failed to mark old version {old_id} as superseded (column may not exist)"
                )

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
                organization_id=org_id,
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
                organization_id=org_id,
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
    memory_key = None
    memory_org_id = None
    try:
        existing = (
            await client.table("conversation_memories")
            .select("value, key, organization_id")
            .eq("id", memory_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if existing and existing.data:
            old_value = existing.data.get("value")
            memory_key = existing.data.get("key")
            memory_org_id = existing.data.get("organization_id")
    except Exception:
        pass

    delete_query = client.table("conversation_memories").delete().eq("user_id", user_id)
    delete_query = (
        delete_query.eq("key", memory_key)
        if memory_key
        else delete_query.eq("id", memory_id)
    )
    result = await delete_query.execute()

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
                organization_id=memory_org_id,
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

    logger.info(
        f"Cleared {count} memories for user {user_id}{f' (category={category})' if category else ''}"
    )
    return count


async def update_memory(
    user_id: str,
    memory_id: str,
    *,
    value: str | None = None,
    visibility: str | None = None,
    lifecycle_state: str | None = None,
    expires_at: str | None = None,
    db: Any = None,
) -> dict | None:
    """Update user controls; content edits create a new immutable version."""
    client = db or supabase
    if not client:
        return None
    existing = (
        await client.table("conversation_memories")
        .select("*")
        .eq("id", memory_id)
        .eq("user_id", user_id)
        .is_("superseded_by", "null")
        .maybe_single()
        .execute()
    )
    if not existing.data:
        return None
    memory = existing.data
    old_value = decrypt_memory_value(memory.get("value", ""))

    if value is not None and value.strip() and value.strip() != old_value:
        return await save_memory(
            user_id=user_id,
            key=memory["key"],
            value=value.strip(),
            category=memory.get("category", "preference"),
            metadata=memory.get("metadata") or {},
            importance=float(memory.get("importance") or 0.5),
            org_id=memory.get("organization_id"),
            db=client,
            valid_from=memory.get("valid_from"),
            valid_until=memory.get("valid_until"),
            fact_type=memory.get("fact_type") or "fact",
            confidence=float(memory.get("confidence") or 1.0),
            visibility=visibility or memory.get("visibility") or "private",
            lifecycle_state=lifecycle_state or "confirmed",
            expires_at=expires_at or memory.get("expires_at"),
            evidence_ref=memory.get("evidence_ref"),
            source="user_explicit",
            extraction_method="user_explicit",
        )

    updates: dict[str, Any] = {"updated_at": datetime.now(UTC).isoformat()}
    if visibility is not None:
        updates["visibility"] = visibility
    if lifecycle_state is not None:
        updates["lifecycle_state"] = lifecycle_state
        if lifecycle_state == "confirmed":
            updates["confirmed_at"] = datetime.now(UTC).isoformat()
        if lifecycle_state == "archived":
            updates["archived_at"] = datetime.now(UTC).isoformat()
    if expires_at is not None:
        updates["expires_at"] = expires_at
    result = (
        await client.table("conversation_memories")
        .update(updates)
        .eq("id", memory_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        return None
    updated = result.data[0] if isinstance(result.data, list) else result.data
    updated["value"] = decrypt_memory_value(updated.get("value", ""))
    try:
        from .audit import log_memory_change

        await log_memory_change(
            memory_id=memory_id,
            user_id=user_id,
            action="UPDATE",
            old_value=old_value,
            new_value=old_value,
            reason="User updated memory controls",
            actor="user_explicit",
            db=client,
            organization_id=memory.get("organization_id"),
        )
    except Exception:
        logger.exception("Memory control audit failed")
    return updated


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
            .select(
                "id, key, value, category, version, importance, created_at, updated_at"
            )
            .eq("user_id", user_id)
            .eq("key", key)
            .order("version", desc=True)
            .limit(limit)
            .execute()
        )
        rows = result.data or []
        for row in rows:
            row["value"] = decrypt_memory_value(row.get("value", ""))
        return rows
    except Exception as e:
        logger.error(f"get_memory_history failed (columns may not exist): {e}")
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
        logger.error(f"_find_semantically_similar RPC failed: {e}")

    return None


_CATEGORY_LIMITS = {
    "preference": 200,
    "episodic": 300,
    "completed_task": 200,
    "tool_correction": 100,
    "reasoning_trace": 150,
}


async def _enforce_memory_limit(
    user_id: str,
    db: Any,
    *,
    category: str,
    max_memories: int = 1200,
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
        total = (
            count_res.count
            if hasattr(count_res, "count") and count_res.count is not None
            else len(count_res.data or [])
        )
        category_limit = _CATEGORY_LIMITS.get(category, 300)
        category_count_res = (
            await db.table("conversation_memories")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("category", category)
            .is_("superseded_by", "null")
            .execute()
        )
        category_total = (
            category_count_res.count
            if getattr(category_count_res, "count", None) is not None
            else len(category_count_res.data or [])
        )
        if total < max_memories and category_total < category_limit:
            return

        # Evict bottom 10% (at least 1) ordered by importance ASC
        active_limit = min(max_memories, category_limit)
        evict_count = max(int(active_limit * 0.1), 1)
        victims = (
            await db.table("conversation_memories")
            .select("id")
            .eq("user_id", user_id)
            .eq("category", category)
            .is_("superseded_by", "null")
            .not_.in_("category", ["explicit_memory", "policy"])
            .order("importance", desc=False)
            .limit(evict_count)
            .execute()
        )
        if victims.data:
            victim_ids = [v["id"] for v in victims.data]
            try:
                await db.table("conversation_memories").update(
                    {
                        "lifecycle_state": "archived",
                        "archived_at": datetime.now(UTC).isoformat(),
                    }
                ).in_("id", victim_ids).execute()
            except Exception:
                await db.table("conversation_memories").delete().in_(
                    "id", victim_ids
                ).execute()
            logger.info(
                "[MemoryLimit] Evicted %d low-importance memories for user %s (total was %d, cap %d)",
                len(victim_ids),
                user_id,
                total,
                max_memories,
            )
    except Exception as e:
        logger.error("[MemoryLimit] Limit enforcement failed (non-fatal): %s", e)
