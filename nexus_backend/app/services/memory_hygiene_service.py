"""Memory hygiene audits for long-running Agents."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class MemoryHygieneService:
    async def audit_memory_hygiene(
        self,
        *,
        db: Any,
        user_id: str,
        org_id: str | None,
        limit: int = 80,
    ) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        audit_status = "healthy"
        audit_error: str | None = None
        if db:
            try:
                query = (
                    db.table("conversation_memories")
                    .select(
                        "id, category, importance, created_at, updated_at, "
                        "last_accessed_at, access_count, lifecycle_state, expires_at, "
                        "superseded_by, metadata"
                    )
                    .eq("user_id", user_id)
                )
                if org_id:
                    query = query.eq("organization_id", org_id)
                result = (
                    await query.order("created_at", desc=True).limit(limit).execute()
                )
                rows = result.data or []
            except Exception as exc:
                audit_status = "degraded"
                audit_error = type(exc).__name__
                logger.exception("Memory hygiene query failed")
        else:
            audit_status = "degraded"
            audit_error = "database_unavailable"

        now = datetime.now(UTC)
        stale = 0
        expired = 0
        compressed = 0
        conflict_candidates = 0
        golden_examples = 0

        for row in rows:
            created_at = self._parse_dt(row.get("created_at"))
            age_days = (now - created_at).days if created_at else 0
            if age_days >= 90:
                stale += 1
            expires_at = self._parse_dt(row.get("expires_at"))
            if row.get("lifecycle_state") == "expired" or (
                expires_at is not None and expires_at <= now
            ):
                expired += 1
            metadata = row.get("metadata") or {}
            if isinstance(metadata, dict) and (
                metadata.get("compressed") or metadata.get("consolidated")
            ):
                compressed += 1
            if row.get("category") == "golden_example":
                golden_examples += 1
            if isinstance(metadata, dict) and (
                metadata.get("conflict_flag") or row.get("superseded_by")
            ):
                conflict_candidates += 1

        hygiene_score = 0 if audit_status == "degraded" else 100
        hygiene_score -= min(35, stale * 3)
        hygiene_score -= min(25, conflict_candidates * 8)
        hygiene_score -= 10 if golden_examples > 20 else 0
        hygiene_score += min(10, compressed)
        hygiene_score = max(0, min(100, hygiene_score))

        recommendations = []
        if stale:
            recommendations.append("对 90 天以上低访问记忆执行降权或 soft-expire。")
        if conflict_candidates:
            recommendations.append(
                "对冲突/被替代记忆建立 superseded_by 链接并降低检索权重。"
            )
        if golden_examples > 20:
            recommendations.append(
                "Golden Examples 数量偏多，建议蒸馏为 5-8 条场景样例。"
            )
        if audit_status == "degraded":
            recommendations.insert(
                0, "记忆健康检查暂不可用，请检查数据库迁移和连接状态。"
            )
        elif not recommendations:
            recommendations.append("记忆状态健康，可继续按生命周期任务自动维护。")

        return {
            "status": audit_status,
            "error": audit_error,
            "sample_size": len(rows),
            "hygiene_score": hygiene_score,
            "stale_memories": stale,
            "expired_memories": expired,
            "compressed_memories": compressed,
            "conflict_candidates": conflict_candidates,
            "golden_examples": golden_examples,
            "recommendations": recommendations,
            "policy": {
                "fresh_memory_days": 30,
                "compress_after_days": 30,
                "soft_expire_after_days": 90,
                "golden_example_target": 8,
            },
        }

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            text = str(value).replace("Z", "+00:00")
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
        except Exception:
            return None


memory_hygiene_service = MemoryHygieneService()
