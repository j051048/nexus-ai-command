"""
Reranker Service — Unified reranking with multiple backend support.

Backends:
- cohere: Cohere Rerank API (highest quality, requires COHERE_API_KEY)
- bge: Local BGE-Reranker via HuggingFace API proxy (fast, no extra API key)
- llm: LLM-based reranking as fallback (existing behavior from VectorService)

Selection logic:
1. If RERANKER_BACKEND is explicitly set → use that backend
2. If COHERE_API_KEY is set → use cohere
3. Else → fallback to llm
"""

import asyncio
import logging
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RerankResult:
    """Result of a rerank operation."""
    documents: list[dict]
    backend_used: str
    latency_ms: float = 0.0


class RerankerService:
    """
    Unified reranker service supporting multiple backends.

    Usage:
        reranker = RerankerService()
        result = await reranker.rerank(query, documents, top_k=5)
        reranked_docs = result.documents
    """

    def __init__(self):
        self._backend = self._resolve_backend()
        logger.info(f"[RerankerService] Initialized with backend: {self._backend}")

    def _resolve_backend(self) -> str:
        """Determine which reranker backend to use."""
        # Explicit setting takes priority
        explicit = getattr(settings, "RERANKER_BACKEND", "").strip().lower()
        if explicit in ("cohere", "bge", "llm"):
            return explicit

        # Auto-detect: prefer cohere if API key is available
        cohere_key = getattr(settings, "COHERE_API_KEY", "").strip()
        if cohere_key:
            return "cohere"

        # Check existing RERANK_PROVIDER setting for backward compatibility
        provider = getattr(settings, "RERANK_PROVIDER", "").strip().lower()
        if provider == "api_reranker":
            return "bge"

        return "llm"

    async def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int = 5,
        user_id: str = None,
    ) -> RerankResult:
        """
        Rerank documents by relevance to query.

        Args:
            query: The search query
            documents: List of dicts with at least a "content" key
            top_k: Number of top results to return
            user_id: Optional user ID for logging or specific backend handling

        Returns:
            RerankResult with reranked documents and metadata
        """
        if not documents or len(documents) <= 1:
            return RerankResult(documents=documents[:top_k], backend_used="passthrough")

        # Skip reranking for very small sets — not worth the latency
        if len(documents) <= 3:
            return RerankResult(documents=documents[:top_k], backend_used="passthrough")

        import time
        start = time.time()

        backend = self._backend
        try:
            if backend == "cohere":
                result_docs = await self._rerank_cohere(query, documents, top_k)
            elif backend == "bge":
                result_docs = await self._rerank_bge(query, documents, top_k)
            elif backend == "llm":
                result_docs = await self._rerank_llm(query, documents, top_k)
            else:
                logger.warning(f"[RerankerService] Unknown backend '{backend}', falling back to llm")
                result_docs = await self._rerank_llm(query, documents, top_k)
                backend = "llm"
        except Exception as e:
            error_msg = str(e) or repr(e) or type(e).__name__
            logger.warning(f"[RerankerService] {backend} failed: {error_msg}, falling back to llm")
            try:
                result_docs = await self._rerank_llm(query, documents, top_k)
                backend = f"llm(fallback from {backend})"
            except Exception as e2:
                logger.warning(f"[RerankerService] LLM fallback also failed: {e2}, returning original order")
                result_docs = documents[:top_k]
                backend = "none(all failed)"

        elapsed_ms = (time.time() - start) * 1000
        logger.info(f"[RerankerService] Reranked {len(documents)} docs via {backend} in {elapsed_ms:.0f}ms")
        return RerankResult(documents=result_docs, backend_used=backend, latency_ms=elapsed_ms)

    # G5 Optimization: Use a shared persistent client for all rerank requests
    _client: "httpx.AsyncClient" = None

    async def _get_client(self, timeout: float = 10.0) -> "httpx.AsyncClient":
        import httpx
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=timeout,
                limits=httpx.Limits(max_connections=50, max_keepalive_connections=20)
            )
        return self._client

    # ── Cohere Backend ─────────────────────────────────────────────────────

    async def _rerank_cohere(
        self, query: str, documents: list[dict], top_k: int
    ) -> list[dict]:
        """Rerank via Cohere Rerank API."""
        api_key = getattr(settings, "COHERE_API_KEY", "").strip()
        if not api_key:
            raise ValueError("COHERE_API_KEY not configured")

        max_docs = getattr(settings, "RERANK_MAX_DOCS", 15)
        timeout = getattr(settings, "RERANK_TIMEOUT", 30)

        doc_texts = [doc.get("content", "")[:1000] for doc in documents[:max_docs]]

        payload = {
            "model": "rerank-v3.5",
            "query": query,
            "documents": doc_texts,
            "top_n": min(top_k, len(doc_texts)),
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        client = await self._get_client(timeout=timeout)
        resp = await client.post(
            "https://api.cohere.com/v2/rerank",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        return self._apply_rerank_indices(documents, results, top_k)

    # ── BGE Backend (via OpenAI-compatible API proxy) ──────────────────────

    async def _rerank_bge(
        self, query: str, documents: list[dict], top_k: int
    ) -> list[dict]:
        """Rerank via BGE-Reranker model through API proxy (Cohere-compatible format)."""
        max_docs = getattr(settings, "RERANK_MAX_DOCS", 15)
        timeout = getattr(settings, "RERANK_TIMEOUT", 30)
        rerank_model = getattr(settings, "RERANK_MODEL", "bge-reranker-v2-m3")

        # Build rerank API URL from base URL
        base_url = (settings.AI_BASE_URL or "https://api.apiyi.com/v1").rstrip("/")
        # Fix: ensure we have /v1/rerank or /rerank correctly
        if "/v1" in base_url:
            url = f"{base_url.split('/v1')[0]}/v1/rerank"
        else:
            url = f"{base_url}/rerank"

        doc_texts = [doc.get("content", "")[:1000] for doc in documents[:max_docs]]

        payload = {
            "model": rerank_model,
            "query": query,
            "documents": doc_texts,
            "top_n": min(top_k, len(doc_texts)),
        }
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }

        client = await self._get_client(timeout=timeout)
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            error_text = resp.text[:200]
            raise RuntimeError(f"BGE rerank failed: status={resp.status_code}, body={error_text}")
        data = resp.json()

        results = data.get("results", [])
        return self._apply_rerank_indices(documents, results, top_k)

    # ── LLM Backend (fallback) ─────────────────────────────────────────────

    async def _rerank_llm(
        self, query: str, documents: list[dict], top_k: int
    ) -> list[dict]:
        """Rerank using LLM to sort documents by relevance (existing VectorService approach)."""
        from openai import AsyncOpenAI

        max_docs = getattr(settings, "RERANK_MAX_DOCS", 8)
        timeout = getattr(settings, "RERANK_TIMEOUT", 8)

        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.AI_BASE_URL,
        )

        doc_texts = []
        for i, doc in enumerate(documents[:max_docs]):
            content = doc.get("content", "")[:500]
            doc_texts.append(f"[{i}] {content}")

        prompt = f"""对以下文档按照与查询的相关性进行排序。
查询: {query}

文档列表:
{chr(10).join(doc_texts)}

请直接返回排序后的文档编号（用逗号分隔），最相关的排在前面。只返回编号，例如: 2,0,4,1,3"""

        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=getattr(settings, "AI_MINI_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0,
            ),
            timeout=timeout,
        )

        ranking_str = response.choices[0].message.content.strip()
        indices = []
        for part in ranking_str.replace(" ", "").split(","):
            try:
                idx = int(part.strip("[]"))
                if 0 <= idx < len(documents):
                    indices.append(idx)
            except ValueError:
                continue

        if indices:
            reranked = []
            seen = set()
            for idx in indices[:top_k]:
                if idx not in seen:
                    reranked.append(documents[idx])
                    seen.add(idx)
            # Backfill
            for i, doc in enumerate(documents):
                if i not in seen and len(reranked) < top_k:
                    reranked.append(doc)
            return reranked

        return documents[:top_k]

    # ── Shared Helper ──────────────────────────────────────────────────────

    @staticmethod
    def _apply_rerank_indices(
        documents: list[dict], results: list[dict], top_k: int
    ) -> list[dict]:
        """Apply Cohere-format rerank results to original document list."""
        reranked = []
        seen: set[int] = set()
        for item in results:
            idx = item.get("index", 0)
            if idx < len(documents) and idx not in seen:
                doc = documents[idx].copy()
                doc["rerank_score"] = item.get("relevance_score", 0)
                reranked.append(doc)
                seen.add(idx)

        # Backfill unseen docs to meet top_k
        for i, doc in enumerate(documents):
            if i not in seen and len(reranked) < top_k:
                reranked.append(doc)

        return reranked[:top_k]


# Module-level singleton
reranker_service = RerankerService()
