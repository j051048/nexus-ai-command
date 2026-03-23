"""Soul Document Service — 灵魂文档编译与缓存。

负责将结构化灵魂文档编译为提示词片段，并通过 Redis 缓存加速。
"""

import logging
from typing import Any

from app.core.database import supabase
from app.core.redis_keys import NS_SOUL_DOC, rk
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)

CACHE_TTL = 3600  # 1 小时


class SoulDocumentService:
    """灵魂文档服务 — 编译 + 缓存 + CRUD 辅助。"""

    # ------------------------------------------------------------------
    # 编译
    # ------------------------------------------------------------------
    @staticmethod
    def compile_soul_prompt(doc: dict) -> str:
        """将结构化字段编译为提示词文本段落。"""
        parts: list[str] = ["【灵魂定义 — 由企业管理者设定，最高优先级遵守】"]

        ai_name = doc.get("ai_name") or "小助手"
        parts.append(f"你的名字叫「{ai_name}」，员工会这样称呼你。")

        field_map = [
            ("identity", "身份定位"),
            ("personality", "性格特征"),
            ("values", "价值观与行为准则"),
            ("language_style", "语言风格"),
            ("taboos", "禁忌与红线（绝对不可违反）"),
        ]
        for key, label in field_map:
            val = doc.get(key)
            if val and val.strip():
                parts.append(f"{label}：{val.strip()}")

        custom = doc.get("custom_instructions")
        if custom and custom.strip():
            parts.append(f"\n企业特别指令：\n{custom.strip()}")

        # 保留核心记忆能力声明（与原 SELF_AWARENESS 的记忆部分对齐）
        parts.append(
            "\n记忆能力：你拥有持续记忆，能记住用户偏好和历史对话。"
            "如果上下文中提供了用户姓名，自然地称呼对方。"
            '绝不说"我无法记住之前的对话"或"我不知道你是谁"。'
        )

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # 缓存读取
    # ------------------------------------------------------------------
    async def get_compiled_prompt(self, org_id: str) -> str | None:
        """获取编译后的灵魂文档（带 Redis 缓存）。返回 None 表示该租户未配置。"""
        if not org_id:
            return None

        cache_key = rk(org_id, NS_SOUL_DOC)

        # 1. Redis 缓存
        cached = await cache_service.get(cache_key)
        if cached is not None:
            return cached if cached != "__NONE__" else None

        # 2. DB 查询
        try:
            res = (
                await supabase.table("soul_documents")
                .select("*")
                .eq("tenant_id", org_id)
                .eq("is_active", True)
                .maybe_single()
                .execute()
            )
            if not res or not res.data:
                # 缓存空结果，避免频繁查 DB
                await cache_service.set(cache_key, "__NONE__", ttl=CACHE_TTL)
                return None

            compiled = self.compile_soul_prompt(res.data)
            await cache_service.set(cache_key, compiled, ttl=CACHE_TTL)
            return compiled
        except Exception as e:
            logger.warning(f"[SoulDocService] Failed to load soul doc for {org_id}: {e}")
            return None

    # ------------------------------------------------------------------
    # 缓存失效
    # ------------------------------------------------------------------
    async def invalidate_cache(self, org_id: str) -> None:
        """清除灵魂文档缓存（upsert 后调用）。"""
        cache_key = rk(org_id, NS_SOUL_DOC)
        try:
            await cache_service.delete(cache_key)
        except Exception as e:
            logger.warning(f"[SoulDocService] Cache invalidation failed: {e}")

    # ------------------------------------------------------------------
    # 原始文档读取
    # ------------------------------------------------------------------
    async def get_raw(self, org_id: str) -> dict[str, Any] | None:
        """获取原始灵魂文档记录。"""
        try:
            res = (
                await supabase.table("soul_documents")
                .select("*")
                .eq("tenant_id", org_id)
                .maybe_single()
                .execute()
            )
            return res.data if res else None
        except Exception as e:
            logger.warning(f"[SoulDocService] get_raw failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------
    async def upsert(self, org_id: str, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """创建或更新灵魂文档。返回 upsert 后的记录。"""
        payload = {
            "tenant_id": org_id,
            "ai_name": data.get("ai_name", "小助手"),
            "identity": data.get("identity"),
            "personality": data.get("personality"),
            "values": data.get("values"),
            "language_style": data.get("language_style"),
            "taboos": data.get("taboos"),
            "custom_instructions": data.get("custom_instructions"),
            "is_active": data.get("is_active", True),
            "updated_by": user_id,
            "updated_at": "now()",
        }

        # 检查是否已存在
        existing = await self.get_raw(org_id)
        if existing:
            res = (
                await supabase.table("soul_documents")
                .update(payload)
                .eq("tenant_id", org_id)
                .execute()
            )
        else:
            payload["created_by"] = user_id
            res = (
                await supabase.table("soul_documents")
                .insert(payload)
                .execute()
            )

        await self.invalidate_cache(org_id)
        return res.data[0] if res.data else payload


soul_document_service = SoulDocumentService()
