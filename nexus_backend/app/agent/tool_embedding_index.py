"""Tool Embedding Index — 语义检索精简工具列表.

懒加载构建所有工具 description 的 embedding 向量，
通过 cosine similarity 返回与用户查询最相关的工具名。
复用 vector_service.embed_text() 基础设施。
"""

import asyncio
import logging
import time

import numpy as np

logger = logging.getLogger(__name__)

# 索引刷新间隔（秒）— 工具注册表变化不频繁
_INDEX_TTL = 3600


class ToolEmbeddingIndex:
    """Singleton index: tool_name → embedding vector."""

    def __init__(self):
        self._embeddings: dict[str, np.ndarray] = {}
        self._built_at: float = 0
        self._building: bool = False
        self._lock = asyncio.Lock()

    async def _build(self) -> None:
        """批量 embed 所有已注册工具的 description。

        Uses batch embedding API to send all texts in ~3 HTTP calls
        instead of 151 individual serial calls.
        """
        from app.agent.node_helpers import get_all_tools_schema
        from app.services.vector_service import vector_service

        schemas = get_all_tools_schema()
        if not schemas:
            return

        texts: list[tuple[str, str]] = []  # (tool_name, description)
        for s in schemas:
            fn = s.get("function", {})
            name = fn.get("name", "")
            desc = fn.get("description", "")
            if name and desc:
                texts.append((name, f"{name}: {desc[:300]}"))

        logger.info("[ToolEmbIdx] Building index for %d tools...", len(texts))
        t0 = time.time()

        # Batch embed all tool descriptions with timeout
        all_descs = [t[1] for t in texts]
        try:
            embeddings_list = await asyncio.wait_for(
                vector_service.embed_texts_batch(
                    all_descs, batch_size=50, timeout=15.0
                ),
                timeout=20.0,
            )
        except TimeoutError:
            logger.warning("[ToolEmbIdx] Batch embedding timed out (20s)")
            return

        new_embeddings: dict[str, np.ndarray] = {}
        for (name, _), emb in zip(texts, embeddings_list, strict=False):
            if emb is not None:
                new_embeddings[name] = np.array(emb, dtype=np.float32)

        if new_embeddings:
            self._embeddings = new_embeddings
            self._built_at = time.time()
            logger.info(
                "[ToolEmbIdx] Index built: %d tools in %.1fs",
                len(new_embeddings),
                time.time() - t0,
            )

    async def _ensure_index(self) -> None:
        """确保索引已构建且未过期。"""
        if self._embeddings and (time.time() - self._built_at < _INDEX_TTL):
            return
        async with self._lock:
            # Double-check after acquiring lock
            if self._embeddings and (time.time() - self._built_at < _INDEX_TTL):
                return
            if self._building:
                return
            self._building = True
            try:
                await self._build()
            finally:
                self._building = False

    async def refresh(self) -> int:
        """Force-rebuild the in-memory semantic tool index."""
        async with self._lock:
            self._building = True
            try:
                await self._build()
            finally:
                self._building = False
        return len(self._embeddings)

    def stats(self) -> dict:
        """Return lightweight health metadata for diagnostics."""
        age_s = time.time() - self._built_at if self._built_at else None
        return {
            "tool_count": len(self._embeddings),
            "built_at": self._built_at,
            "age_s": age_s,
            "ttl_s": _INDEX_TTL,
        }

    async def retrieve(
        self,
        query: str,
        top_k: int = 12,
        min_score: float = 0.25,
        candidate_names: set[str] | None = None,
    ) -> list[tuple[str, float]]:
        """返回与 query 语义最相关的工具列表 [(tool_name, score)]。

        Args:
            query: 用户查询文本
            top_k: 最多返回数量
            min_score: 最低相似度阈值
            candidate_names: 如果提供，只在这些工具中检索
        """
        await self._ensure_index()
        if not self._embeddings:
            return []

        from app.services.vector_service import vector_service

        query_vec = await vector_service.embed_text(query)
        if query_vec is None:
            return []

        q = np.array(query_vec, dtype=np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []
        q = q / q_norm

        scores: list[tuple[str, float]] = []
        for name, vec in self._embeddings.items():
            if candidate_names and name not in candidate_names:
                continue
            v_norm = np.linalg.norm(vec)
            if v_norm == 0:
                continue
            sim = float(np.dot(q, vec / v_norm))
            if sim >= min_score:
                scores.append((name, sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# Singleton
tool_embedding_index = ToolEmbeddingIndex()
