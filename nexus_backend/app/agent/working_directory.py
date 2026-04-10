"""
Working Directory (中期记忆) — 跨会话持久化的中间状态存储。

与 SharedBlackboard（单会话内存）不同，WorkingDirectory 将中间状态
持久化到 conversation_memories 表（category='working_state'），
支持 TTL 过期、自动清理，在会话边界之间保持状态。

复用 conversation_memories 表，与 skill_library (category='skill') 同模式。
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

_CATEGORY = "working_state"
_KEY_PREFIX = "wd:"


class WorkingDirectory:
    """跨会话中间状态存储，基于 conversation_memories 表。"""

    async def save(
        self,
        user_id: str,
        org_id: str,
        key: str,
        value: Any,
        metadata: dict | None = None,
        ttl_hours: float = 72,
    ) -> bool:
        """保存一个中间状态。value 必须是 JSON 可序列化的。

        Returns:
            True 表示保存成功，False 表示失败。
        """
        try:
            from app.core.database import supabase as db

            if not db:
                logger.warning("[WorkingDirectory] Database not configured")
                return False

            now = datetime.now(UTC)
            expires_at = (now + timedelta(hours=ttl_hours)).isoformat()
            full_key = f"{_KEY_PREFIX}{key}"

            meta = dict(metadata) if metadata else {}
            meta["expires_at"] = expires_at
            meta["ttl_hours"] = ttl_hours

            value_json = json.dumps(value, ensure_ascii=False)

            # upsert: 检查是否已存在
            existing = (
                await db.table("conversation_memories")
                .select("id")
                .eq("user_id", user_id)
                .eq("key", full_key)
                .eq("category", _CATEGORY)
                .limit(1)
                .execute()
            )

            if existing.data:
                await (
                    db.table("conversation_memories")
                    .update(
                        {
                            "value": value_json,
                            "metadata": meta,
                            "organization_id": org_id,
                            "updated_at": now.isoformat(),
                        }
                    )
                    .eq("id", existing.data[0]["id"])
                    .execute()
                )
            else:
                await (
                    db.table("conversation_memories")
                    .insert(
                        {
                            "user_id": user_id,
                            "organization_id": org_id,
                            "category": _CATEGORY,
                            "key": full_key,
                            "value": value_json,
                            "metadata": meta,
                            "importance": 0.3,
                        }
                    )
                    .execute()
                )

            logger.debug(f"[WorkingDirectory] Saved: {full_key} (ttl={ttl_hours}h)")
            return True

        except Exception as e:
            logger.warning(f"[WorkingDirectory] Save failed for key={key}: {e}")
            return False

    async def load(self, user_id: str, key: str) -> dict | None:
        """加载一个中间状态。过期或不存在返回 None。

        成功加载时更新 access_count 和 last_accessed_at。
        """
        try:
            from app.core.database import supabase as db

            if not db:
                return None

            full_key = f"{_KEY_PREFIX}{key}"

            result = (
                await db.table("conversation_memories")
                .select("id, value, metadata, access_count")
                .eq("user_id", user_id)
                .eq("key", full_key)
                .eq("category", _CATEGORY)
                .limit(1)
                .execute()
            )

            if not result.data:
                return None

            row = result.data[0]
            meta = row.get("metadata") or {}

            # 检查 TTL 过期
            expires_at_str = meta.get("expires_at")
            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
                if datetime.now(UTC) > expires_at:
                    logger.debug(f"[WorkingDirectory] Expired: {full_key}")
                    return None

            # 更新访问计数
            now = datetime.now(UTC)
            await (
                db.table("conversation_memories")
                .update(
                    {
                        "access_count": (row.get("access_count") or 0) + 1,
                        "last_accessed_at": now.isoformat(),
                    }
                )
                .eq("id", row["id"])
                .execute()
            )

            # 解析 value
            try:
                value = json.loads(row.get("value", "null"))
            except (json.JSONDecodeError, TypeError):
                value = row.get("value")

            return {
                "key": key,
                "value": value,
                "metadata": meta,
            }

        except Exception as e:
            logger.warning(f"[WorkingDirectory] Load failed for key={key}: {e}")
            return None

    async def list_active(self, user_id: str, limit: int = 20) -> list[dict]:
        """列出用户所有未过期的工作状态。"""
        try:
            from app.core.database import supabase as db

            if not db:
                return []

            result = (
                await db.table("conversation_memories")
                .select("key, value, metadata, access_count, created_at, updated_at")
                .eq("user_id", user_id)
                .eq("category", _CATEGORY)
                .order("updated_at", desc=True)
                .limit(limit)
                .execute()
            )

            if not result.data:
                return []

            now = datetime.now(UTC)
            active: list[dict] = []

            for row in result.data:
                meta = row.get("metadata") or {}
                expires_at_str = meta.get("expires_at")
                if expires_at_str:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if now > expires_at:
                        continue

                raw_key = row.get("key", "")
                user_key = (
                    raw_key[len(_KEY_PREFIX) :]
                    if raw_key.startswith(_KEY_PREFIX)
                    else raw_key
                )

                try:
                    value = json.loads(row.get("value", "null"))
                except (json.JSONDecodeError, TypeError):
                    value = row.get("value")

                active.append(
                    {
                        "key": user_key,
                        "value": value,
                        "metadata": meta,
                        "access_count": row.get("access_count", 0),
                        "created_at": row.get("created_at"),
                        "updated_at": row.get("updated_at"),
                    }
                )

            return active

        except Exception as e:
            logger.warning(f"[WorkingDirectory] list_active failed: {e}")
            return []

    async def delete(self, user_id: str, key: str) -> bool:
        """删除一个工作状态。"""
        try:
            from app.core.database import supabase as db

            if not db:
                return False

            full_key = f"{_KEY_PREFIX}{key}"

            await (
                db.table("conversation_memories")
                .delete()
                .eq("user_id", user_id)
                .eq("key", full_key)
                .eq("category", _CATEGORY)
                .execute()
            )

            logger.debug(f"[WorkingDirectory] Deleted: {full_key}")
            return True

        except Exception as e:
            logger.warning(f"[WorkingDirectory] Delete failed for key={key}: {e}")
            return False

    async def cleanup_expired(self, user_id: str) -> int:
        """清理用户所有已过期的工作状态。

        Returns:
            删除的记录数。
        """
        try:
            from app.core.database import supabase as db

            if not db:
                return 0

            # 拉取该用户所有 working_state 记录，检查 TTL
            result = (
                await db.table("conversation_memories")
                .select("id, metadata")
                .eq("user_id", user_id)
                .eq("category", _CATEGORY)
                .execute()
            )

            if not result.data:
                return 0

            now = datetime.now(UTC)
            expired_ids: list[str] = []

            for row in result.data:
                meta = row.get("metadata") or {}
                expires_at_str = meta.get("expires_at")
                if not expires_at_str:
                    continue
                expires_at = datetime.fromisoformat(expires_at_str)
                if now > expires_at:
                    expired_ids.append(row["id"])

            if not expired_ids:
                return 0

            # 批量删除
            for eid in expired_ids:
                await db.table("conversation_memories").delete().eq("id", eid).execute()

            logger.info(
                f"[WorkingDirectory] Cleaned up {len(expired_ids)} expired states for user={user_id}"
            )
            return len(expired_ids)

        except Exception as e:
            logger.warning(f"[WorkingDirectory] cleanup_expired failed: {e}")
            return 0


# 全局单例
working_directory = WorkingDirectory()
