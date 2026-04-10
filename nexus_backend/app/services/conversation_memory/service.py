"""
Item 13: AI Conversation Memory Enhancement Service

Provides long-term memory capabilities for the AI agent.
Tracks user preferences, explicit memories, and usage patterns
using a rule-based extraction engine (no LLM calls).

This is the main service class that delegates to focused sub-modules:
- storage: memory CRUD operations
- retrieval: querying, searching, context building
- embedding: vector embedding generation
- cleanup: decay scoring, cleanup, importance re-evaluation
- extraction: preference extraction (regex + LLM)
- org_memory: organization-level memories
- consolidation: memory consolidation ("sleep cycle")
- episodic: episodic memory service
"""

from typing import Any

from . import cleanup, consolidation, extraction, org_memory, retrieval, storage
from .embedding import generate_embedding


class ConversationMemoryService:
    """AI 会话长期记忆服务"""

    # ─── 记忆 CRUD ───────────────────────────────────────────────

    async def save_memory(
        self,
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
        **kwargs,
    ) -> dict:
        """保存用户记忆条目（upsert by user_id + key），同时生成 embedding 向量"""
        return await storage.save_memory(
            user_id=user_id,
            key=key,
            value=value,
            category=category,
            metadata=metadata,
            importance=importance,
            org_id=org_id,
            db=db,
            enriched_value=enriched_value,
            valid_from=valid_from,
            **kwargs,
        )

    async def _generate_embedding(
        self, text: str, org_id: str | None = None
    ) -> list[float] | None:
        """Generate embedding vector for memory text. Returns None on failure."""
        return await generate_embedding(text, org_id)

    async def get_memories(
        self,
        user_id: str,
        category: str | None = None,
        limit: int = 20,
        db: Any = None,
    ) -> list[dict]:
        """获取用户记忆列表"""
        return await retrieval.get_memories(
            user_id=user_id, category=category, limit=limit, db=db
        )

    async def search_memories(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
        org_id: str | None = None,
        db: Any = None,
    ) -> list[dict]:
        """搜索相关记忆（混合检索：embedding 语义搜索 + 关键字匹配）"""
        return await retrieval.search_memories(
            user_id=user_id,
            query=query,
            limit=limit,
            org_id=org_id,
            db=db,
        )

    async def delete_memory(
        self,
        user_id: str,
        memory_id: str,
        db: Any = None,
    ) -> bool:
        """删除单条记忆"""
        return await storage.delete_memory(user_id=user_id, memory_id=memory_id, db=db)

    async def clear_memories(
        self,
        user_id: str,
        category: str | None = None,
        db: Any = None,
    ) -> int:
        """清除记忆（可按分类清除）"""
        return await storage.clear_memories(user_id=user_id, category=category, db=db)

    # ─── 偏好自动提取（规则引擎 + LLM 增强）─────────────────────

    async def extract_preferences(
        self,
        user_id: str,
        messages: list[dict[str, str]],
        org_id: str | None = None,
        db: Any = None,
        *,
        is_subtask: bool = False,
    ) -> list[dict]:
        """从对话中自动提取用户偏好。"""
        return await extraction.extract_preferences(
            user_id=user_id,
            messages=messages,
            org_id=org_id,
            db=db,
            is_subtask=is_subtask,
        )

    async def _extract_with_llm(
        self,
        messages: list[dict[str, str]],
    ) -> list[dict]:
        """Use LLM to extract implicit preferences and facts from conversation."""
        return await extraction.extract_with_llm(messages)

    # ─── Organization Memory ─────────────────────────────────────

    async def save_org_memory(
        self,
        org_id: str,
        category: str,
        key: str,
        value: str,
        user_id: str | None = None,
        metadata: dict | None = None,
        db: Any = None,
    ) -> dict | None:
        """Save an organization-level memory visible to all users in the tenant."""
        return await org_memory.save_org_memory(
            org_id=org_id,
            category=category,
            key=key,
            value=value,
            user_id=user_id,
            metadata=metadata,
            db=db,
        )

    async def get_org_memories(
        self,
        org_id: str,
        category: str | None = None,
        limit: int = 50,
        db: Any = None,
    ) -> list[dict]:
        """Get organization-level memories."""
        return await org_memory.get_org_memories(
            org_id=org_id, category=category, limit=limit, db=db
        )

    async def search_org_memories(
        self,
        org_id: str,
        query: str,
        limit: int = 10,
        db: Any = None,
    ) -> list[dict]:
        """Search organization memories by keyword."""
        return await org_memory.search_org_memories(
            org_id=org_id, query=query, limit=limit, db=db
        )

    async def delete_org_memory(
        self,
        org_id: str,
        memory_id: str,
        db: Any = None,
    ) -> bool:
        """Delete a specific organization memory."""
        return await org_memory.delete_org_memory(
            org_id=org_id, memory_id=memory_id, db=db
        )

    async def build_org_memory_context(
        self,
        org_id: str,
        query: str | None = None,
        db: Any = None,
    ) -> str:
        """Build organization memory context string for injection into system prompt."""
        return await org_memory.build_org_memory_context(
            org_id=org_id, query=query, db=db
        )

    async def extract_org_memories(
        self,
        org_id: str,
        user_id: str,
        message: str,
        ai_response: str,
        db: Any = None,
    ) -> list[dict]:
        """Extract potential organization-level knowledge from conversations."""
        return await extraction.extract_org_memories(
            org_id=org_id,
            user_id=user_id,
            message=message,
            ai_response=ai_response,
            db=db,
        )

    # ─── 记忆上下文构建 ──────────────────────────────────────────

    async def build_memory_context(
        self,
        user_id: str,
        current_query: str,
        db: Any = None,
        complexity: str | None = None,
    ) -> str:
        """构建记忆上下文，注入到 system prompt 中。"""
        return await retrieval.build_memory_context(
            user_id=user_id, current_query=current_query, db=db, complexity=complexity
        )

    # ─── P0-2: Memory Decay ─────────────────────────────────────

    def _mmr_rerank(
        self,
        memories: list[dict],
        limit: int,
        lambda_param: float = 0.7,
    ) -> list[dict]:
        """MMR (Maximal Marginal Relevance) diversity reranking."""
        return cleanup.mmr_rerank(memories, limit, lambda_param)

    def _compute_decay_score(self, memory: dict) -> float:
        """Compute a decay-weighted importance score with surprise bonus."""
        return cleanup.compute_decay_score(memory)

    async def cleanup_decayed_memories(
        self,
        min_age_days: int = 30,
        score_threshold: float = 0.1,
        batch_size: int = 200,
        db: Any = None,
    ) -> dict:
        """Remove low-score memories that are older than min_age_days."""
        return await cleanup.cleanup_decayed_memories(
            min_age_days=min_age_days,
            score_threshold=score_threshold,
            batch_size=batch_size,
            db=db,
        )

    async def reevaluate_importance(
        self,
        batch_size: int = 200,
        db: Any = None,
    ) -> dict:
        """Periodically adjust memory importance based on access patterns."""
        return await cleanup.reevaluate_importance(batch_size=batch_size, db=db)

    # ─── Memory Consolidation ────────────────────────────────────

    async def consolidate_user_memories(
        self,
        user_id: str,
        org_id: str | None = None,
        batch_size: int = 30,
        db: Any = None,
    ) -> dict:
        """Consolidate a user's unconsolidated memories into cross-memory insights."""
        return await consolidation.consolidate_user_memories(
            user_id=user_id,
            org_id=org_id,
            batch_size=batch_size,
            db=db,
        )

    async def _write_connections(
        self,
        memories: list[dict],
        connections: list[dict],
        client: Any,
    ) -> None:
        """Write bidirectional connections between memories from LLM analysis."""
        return await consolidation._write_connections(memories, connections, client)

    async def search_consolidations(
        self,
        user_id: str,
        query: str,
        limit: int = 3,
        org_id: str | None = None,
        db: Any = None,
    ) -> list[dict]:
        """Search consolidated insights via embedding similarity."""
        return await retrieval.search_consolidations(
            user_id=user_id,
            query=query,
            limit=limit,
            org_id=org_id,
            db=db,
        )

    async def _expand_top_connections(
        self,
        memories: list[dict],
        user_id: str,
        limit: int = 3,
        db: Any = None,
    ) -> list[dict]:
        """1-hop expansion: fetch connected memories for top results."""
        return await retrieval._expand_top_connections(
            memories=memories,
            user_id=user_id,
            limit=limit,
            db=db,
        )
