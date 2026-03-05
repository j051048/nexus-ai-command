"""
P2 Enhancement: Context Preservation Service

Implements persistent context management for AI conversations.
Fixes Issue #19: Context lost across page refresh.
"""

import contextlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ContextScope(Enum):
    """Scope of context preservation."""

    SESSION = "session"  # Current browser session
    USER = "user"  # User-level, cross-session
    ORGANIZATION = "org"  # Organization-level
    GLOBAL = "global"  # System-wide


@dataclass
class ContextEntry:
    """A single context entry."""

    key: str
    value: Any
    scope: ContextScope
    owner_id: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    expires_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    ttl_seconds: int = 3600  # Default 1 hour


class ContextPreservationService:
    """
    P2 Enhancement: Persistent context for AI conversations.

    Features:
    - Multi-scope context storage
    - Automatic expiration
    - Context compression
    - Cross-session persistence
    - Priority-based eviction
    """

    # Default TTL for different scopes
    DEFAULT_TTL = {
        ContextScope.SESSION: 1800,  # 30 minutes
        ContextScope.USER: 86400,  # 24 hours
        ContextScope.ORGANIZATION: 604800,  # 7 days
        ContextScope.GLOBAL: 2592000,  # 30 days
    }

    # Max entries per scope
    MAX_ENTRIES = {
        ContextScope.SESSION: 100,
        ContextScope.USER: 500,
        ContextScope.ORGANIZATION: 1000,
        ContextScope.GLOBAL: 10000,
    }

    def __init__(self, redis_client=None, db_client=None):
        self.redis = redis_client
        self.db = db_client
        self._memory_cache: dict[str, ContextEntry] = {}
        self._dirty_keys: set = set()

    def _generate_key(self, scope: ContextScope, owner_id: str, key: str) -> str:
        """Generate storage key."""
        return f"context:{scope.value}:{owner_id}:{key}"

    async def set(
        self,
        key: str,
        value: Any,
        scope: ContextScope = ContextScope.USER,
        owner_id: str = None,
        ttl_seconds: int = None,
        metadata: dict = None,
    ) -> ContextEntry:
        """
        Set a context value.

        Args:
            key: Context key
            value: Context value (will be JSON serialized)
            scope: Scope of context
            owner_id: Owner identifier (user_id, session_id, org_id)
            ttl_seconds: Time to live in seconds
            metadata: Additional metadata

        Returns:
            ContextEntry object
        """
        if not owner_id:
            owner_id = "default"

        ttl = ttl_seconds or self.DEFAULT_TTL.get(scope, 3600)
        expires_at = None
        if ttl > 0:
            expires_at = (datetime.utcnow() + timedelta(seconds=ttl)).isoformat()

        entry = ContextEntry(
            key=key,
            value=value,
            scope=scope,
            owner_id=owner_id,
            expires_at=expires_at,
            metadata=metadata or {},
            ttl_seconds=ttl,
        )

        storage_key = self._generate_key(scope, owner_id, key)

        # Store in memory cache
        self._memory_cache[storage_key] = entry
        self._dirty_keys.add(storage_key)

        # Store in Redis if available
        if self.redis:
            try:
                await self.redis.setex(storage_key, ttl, json.dumps(entry.__dict__, default=str, ensure_ascii=False))
            except Exception as e:
                logger.warning(f"Redis context store failed: {e}")

        # Persist to database if available
        if self.db and scope in [ContextScope.USER, ContextScope.ORGANIZATION]:
            await self._persist_to_db(entry)

        logger.debug(f"Context set: {storage_key}")
        return entry

    async def get(
        self, key: str, scope: ContextScope = ContextScope.USER, owner_id: str = None, default: Any = None
    ) -> Any | None:
        """
        Get a context value.

        Returns:
            The context value or default if not found
        """
        if not owner_id:
            owner_id = "default"

        storage_key = self._generate_key(scope, owner_id, key)

        # Check memory cache
        if storage_key in self._memory_cache:
            entry = self._memory_cache[storage_key]
            if not self._is_expired(entry):
                return entry.value
            else:
                del self._memory_cache[storage_key]

        # Check Redis
        if self.redis:
            try:
                data = await self.redis.get(storage_key)
                if data:
                    entry_dict = json.loads(data)
                    entry = ContextEntry(**entry_dict)
                    self._memory_cache[storage_key] = entry
                    return entry.value
            except Exception as e:
                logger.warning(f"Redis context get failed: {e}")

        # Check database
        if self.db:
            entry = await self._get_from_db(scope, owner_id, key)
            if entry:
                self._memory_cache[storage_key] = entry
                return entry.value

        return default

    async def delete(self, key: str, scope: ContextScope = ContextScope.USER, owner_id: str = None):
        """Delete a context value."""
        if not owner_id:
            owner_id = "default"

        storage_key = self._generate_key(scope, owner_id, key)

        # Remove from memory
        if storage_key in self._memory_cache:
            del self._memory_cache[storage_key]

        # Remove from Redis
        if self.redis:
            with contextlib.suppress(Exception):
                await self.redis.delete(storage_key)

        # Remove from database
        if self.db:
            await self._delete_from_db(scope, owner_id, key)

    async def get_all(self, scope: ContextScope, owner_id: str = None, prefix: str = None) -> dict[str, Any]:
        """
        Get all context values for a scope/owner.

        Args:
            scope: Context scope
            owner_id: Owner identifier
            prefix: Key prefix filter

        Returns:
            Dict of key-value pairs
        """
        if not owner_id:
            owner_id = "default"

        result = {}
        pattern = f"context:{scope.value}:{owner_id}:"
        if prefix:
            pattern += prefix

        # Get from memory cache
        for key, entry in self._memory_cache.items():
            if key.startswith(pattern) and not self._is_expired(entry):
                result[entry.key] = entry.value

        # Get from Redis
        if self.redis:
            try:
                keys = await self.redis.keys(f"{pattern}*")
                for key in keys:
                    if isinstance(key, bytes):
                        key = key.decode()
                    if key not in self._memory_cache:
                        data = await self.redis.get(key)
                        if data:
                            entry_dict = json.loads(data)
                            entry = ContextEntry(**entry_dict)
                            if not self._is_expired(entry):
                                result[entry.key] = entry.value
            except Exception as e:
                logger.warning(f"Redis get_all failed: {e}")

        return result

    def _is_expired(self, entry: ContextEntry) -> bool:
        """Check if an entry is expired."""
        if not entry.expires_at:
            return False
        return datetime.utcnow() > datetime.fromisoformat(entry.expires_at)

    async def _persist_to_db(self, entry: ContextEntry):
        """Persist entry to database."""
        if not self.db:
            return

        try:
            await (
                self.db.table("ai_context_store")
                .upsert(
                    {
                        "scope": entry.scope.value,
                        "owner_id": entry.owner_id,
                        "key": entry.key,
                        "value": json.dumps(entry.value, ensure_ascii=False),
                        "expires_at": entry.expires_at,
                        "metadata": entry.metadata,
                    }
                )
                .execute()
            )
        except Exception as e:
            logger.warning(f"DB persist failed: {e}")

    async def _get_from_db(self, scope: ContextScope, owner_id: str, key: str) -> ContextEntry | None:
        """Get entry from database."""
        if not self.db:
            return None

        try:
            result = (
                await self.db.table("ai_context_store")
                .select("*")
                .eq("scope", scope.value)
                .eq("owner_id", owner_id)
                .eq("key", key)
                .gt("expires_at", datetime.utcnow().isoformat())
                .single()
                .execute()
            )

            if result.data:
                return ContextEntry(
                    key=result.data["key"],
                    value=json.loads(result.data["value"]),
                    scope=ContextScope(result.data["scope"]),
                    owner_id=result.data["owner_id"],
                    expires_at=result.data["expires_at"],
                    metadata=result.data["metadata"],
                )
        except Exception:
            pass

        return None

    async def _delete_from_db(self, scope: ContextScope, owner_id: str, key: str):
        """Delete entry from database."""
        if not self.db:
            return

        with contextlib.suppress(Exception):
            await (
                self.db.table("ai_context_store")
                .delete()
                .eq("scope", scope.value)
                .eq("owner_id", owner_id)
                .eq("key", key)
                .execute()
            )

    # Conversation-specific helpers

    async def save_conversation_state(
        self, session_id: str, messages: list[dict], current_intent: str = None, metadata: dict = None
    ):
        """Save full conversation state for recovery."""
        await self.set(
            key="conversation",
            value={"messages": messages, "current_intent": current_intent, "message_count": len(messages)},
            scope=ContextScope.SESSION,
            owner_id=session_id,
            metadata=metadata,
        )

    async def restore_conversation(self, session_id: str) -> dict | None:
        """Restore conversation state."""
        return await self.get(key="conversation", scope=ContextScope.SESSION, owner_id=session_id)

    async def save_user_preference(self, user_id: str, preference_key: str, value: Any):
        """Save user preference."""
        await self.set(
            key=f"pref:{preference_key}",
            value=value,
            scope=ContextScope.USER,
            owner_id=user_id,
            ttl_seconds=self.DEFAULT_TTL[ContextScope.USER],
        )

    async def get_user_preference(self, user_id: str, preference_key: str, default: Any = None) -> Any:
        """Get user preference."""
        return await self.get(key=f"pref:{preference_key}", scope=ContextScope.USER, owner_id=user_id, default=default)

    async def compress_context(self, messages: list[dict], max_tokens: int = 4000) -> list[dict]:
        """
        Compress conversation context to fit within token limit.
        """
        if not messages:
            return messages

        # Estimate tokens (rough: 1 token ~ 4 chars)
        def estimate_tokens(msg):
            return len(str(msg.get("content", ""))) // 4

        total_tokens = sum(estimate_tokens(m) for m in messages)

        if total_tokens <= max_tokens:
            return messages

        # Keep recent messages + summary of older ones
        keep_recent = 5
        recent = messages[-keep_recent:]
        older = messages[:-keep_recent]

        # Create summary of older messages
        summary = {
            "role": "system",
            "content": f"[历史对话摘要] 共{len(older)}条消息，关键信息: {self._extract_key_info(older)}",
        }

        return [summary] + recent

    def _extract_key_info(self, messages: list[dict]) -> str:
        """Extract key information from messages for summary."""
        key_points = []
        for msg in messages:
            content = str(msg.get("content", ""))
            # Extract entities, decisions, etc.
            if len(content) > 50:
                key_points.append(content[:100] + "...")

        return "; ".join(key_points[:3]) if key_points else "无关键信息"

    async def cleanup_expired(self):
        """Clean up expired entries."""
        datetime.utcnow()
        expired_keys = []

        for key, entry in self._memory_cache.items():
            if self._is_expired(entry):
                expired_keys.append(key)

        for key in expired_keys:
            del self._memory_cache[key]

        logger.info(f"Cleaned up {len(expired_keys)} expired context entries")
        return len(expired_keys)


# Global instance
context_preservation_service = ContextPreservationService()
