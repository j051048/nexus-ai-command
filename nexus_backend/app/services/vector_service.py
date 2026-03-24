import hashlib
import logging
import re
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.database import supabase

logger = logging.getLogger(__name__)

# P1: Embedding Model Versioning — Track model changes to detect stale embeddings
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_MODEL_VERSION = "2026-03"
_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-large"
# All DB vector columns are vector(1536); force this dimension to avoid mismatch
_EMBEDDING_DIMENSIONS = 1536

# Reranker configuration — read from settings at call time, not import time
# (settings.RERANK_ENABLED, settings.RERANK_PROVIDER, settings.RERANK_MODEL, etc.)

# Timeout for OpenAI API calls (embedding + rerank)
_OPENAI_TIMEOUT = float(getattr(settings, "VECTOR_OPENAI_TIMEOUT", 15))


def escape_like_pattern(value: str) -> str:
    """P0 Security: Escape special characters in LIKE patterns to prevent SQL injection"""
    if not value:
        return value
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def sanitize_search_query(query: str, max_length: int = 500) -> str:
    """P0 Security: Sanitize and validate search query input"""
    if not query:
        return ""
    query = query[:max_length]
    query = re.sub(r'[;\-\-\'"\\]', " ", query)
    query = " ".join(query.split())
    return query.strip()


class VectorServiceError(Exception):
    """Custom exception for VectorService errors"""

    pass


class MissingOrgIdError(VectorServiceError):
    """Raised when org_id is not provided - P0 Security requirement"""

    pass


class VectorService:
    """
    Interface for Vector Database operations using Supabase pgvector.
    Enhanced with Hybrid Search (Vector + Keyword), RRF Fusion, and Cross-Encoder Reranking.

    P0 Security: org_id is MANDATORY for all search operations to prevent cross-tenant data leakage.
    """

    _EMBED_CACHE_MAX = 500  # max cached embeddings (in-process LRU)
    _EMBED_CACHE_TTL = 3600  # 1 hour TTL for embedding cache entries
    _embed_cache: OrderedDict[str, tuple[list[float], float]] = OrderedDict()  # key -> (embedding, timestamp)

    _DOC_TYPE_LABELS = {
        "tender": "招标文件",
        "bid": "投标文件",
        "product": "产品资料",
        "contract": "合同",
        "proposal": "方案文档",
        "invoice": "发票",
    }

    @staticmethod
    async def _get_embedding_config(org_id: str = "default") -> tuple[str, str, str]:
        """Resolve embedding model dynamically via gateway. Returns (api_key, base_url, model)."""
        try:
            from app.services.llm_helpers import resolve_embedding_config

            config = await resolve_embedding_config(org_id)
            return config["api_key"], config["base_url"], config["model"]
        except Exception:
            return (
                settings.OPENAI_API_KEY,
                getattr(settings, "AI_BASE_URL", "https://api.openai.com/v1"),
                _DEFAULT_EMBEDDING_MODEL,
            )

    @staticmethod
    def _get_doc_type_label(item: dict) -> str:
        """Get a Chinese label for the document type, if available."""
        doc_type = item.get("doc_type") or ""
        if not doc_type:
            meta = item.get("metadata") or item.get("doc_metadata") or {}
            doc_type = meta.get("doc_type", "")
        return VectorService._DOC_TYPE_LABELS.get(doc_type, "")

    async def _rerank_with_api(
        self, query: str, documents: list[dict], top_n: int = 5
    ) -> list[dict]:
        """
        Use dedicated reranker model (bge-reranker-v2-m3) via API proxy.
        Expected latency: ~100ms vs 2-8s for LLM reranking.
        Falls back gracefully — caller should catch exceptions.
        """
        if not documents or len(documents) <= 1:
            return documents
        if len(documents) <= 3:
            return documents[:top_n]

        import httpx

        max_docs = settings.RERANK_MAX_DOCS
        rerank_timeout = settings.RERANK_TIMEOUT
        rerank_model = settings.RERANK_MODEL

        # Build rerank API URL from base URL
        base_url = (settings.AI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
        # Strip /v1 suffix to get the root, then append /v1/rerank
        base_root = base_url.rsplit("/v1", 1)[0] if base_url.endswith("/v1") else base_url
        url = f"{base_root}/v1/rerank"

        doc_texts = [doc.get("content", "")[:500] for doc in documents[:max_docs]]

        payload = {
            "model": rerank_model,
            "query": query,
            "documents": doc_texts,
            "top_n": min(top_n, len(doc_texts)),
        }
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=rerank_timeout) as http_client:
            resp = await http_client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # Parse Cohere-compatible response: {results: [{index, relevance_score}, ...]}
        results = data.get("results", [])
        reranked = []
        seen = set()
        for item in results:
            idx = item.get("index", 0)
            if idx < len(documents) and idx not in seen:
                doc = documents[idx].copy()
                doc["rerank_score"] = item.get("relevance_score", 0)
                reranked.append(doc)
                seen.add(idx)

        # Backfill unseen docs to meet top_n
        for i, doc in enumerate(documents):
            if i not in seen and len(reranked) < top_n:
                reranked.append(doc)

        return reranked[:top_n]

    async def _rerank_with_llm(
        self, query: str, documents: list[dict], client: AsyncOpenAI, top_n: int = 5
    ) -> list[dict]:
        """
        Use LLM to rerank documents based on relevance to query.
        This is a lightweight cross-encoder alternative using GPT.
        Skipped when document count is small (<=3) to save latency.
        """
        if not documents or len(documents) <= 1:
            return documents

        # Skip reranking for small result sets — not worth the LLM call latency
        if len(documents) <= 3:
            return documents[:top_n]

        # P2: Use configurable max docs and timeout
        max_docs = getattr(settings, "RERANK_MAX_DOCS", 8)
        rerank_timeout = getattr(settings, "RERANK_TIMEOUT", 8)

        try:
            doc_texts = []
            for i, doc in enumerate(documents[:max_docs]):
                content = doc.get("content", "")[:500]
                doc_texts.append(f"[{i}] {content}")

            prompt = f"""对以下文档按照与查询的相关性进行排序。
查询: {query}

文档列表:
{chr(10).join(doc_texts)}

请直接返回排序后的文档编号（用逗号分隔），最相关的排在前面。只返回编号，例如: 2,0,4,1,3"""

            import asyncio

            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=getattr(self, "_rerank_model", "gpt-4o-mini"),
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=50,
                    temperature=0,
                ),
                timeout=rerank_timeout,
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
                for idx in indices[:top_n]:
                    if idx not in seen:
                        reranked.append(documents[idx])
                        seen.add(idx)
                for i, doc in enumerate(documents):
                    if i not in seen and len(reranked) < top_n:
                        reranked.append(doc)
                return reranked

        except Exception as e:
            logger.warning(f"LLM reranking failed, using RRF scores: {e}")

        return documents[:top_n]

    async def search(
        self,
        query: str,
        user_id: str,
        limit: int = 3,
        config: dict = None,
        org_id: str = None,  # P0: This should be required, but kept optional for backward compat
        require_org_id: bool = True,  # P0: New param to enforce org_id requirement
    ) -> str:
        """
        Semantic search in the vector DB.
        Returns a formatted string of results.

        P0 Security Fix: org_id is now MANDATORY in production.
        - If require_org_id=True (default), search will fail without org_id
        - In development mode, a warning is logged but search proceeds
        - This prevents cross-tenant data leakage
        """
        query = sanitize_search_query(query)
        if not query:
            return "请提供有效的搜索关键词。"

        # P0 Security: Enforce org_id requirement
        if not org_id:
            if require_org_id or settings.IS_PRODUCTION:
                logger.error(f"P0 Security Violation: Vector search called without org_id (user_id={user_id})")
                return "搜索失败：缺少组织信息。请确保您已正确登录并属于某个组织。"
            else:
                logger.warning(f"Vector search called without org_id in development mode (user_id={user_id})")

        limit = min(max(1, limit), 10)
        api_key = (config or {}).get("api_key") or settings.OPENAI_API_KEY

        raw_url = (config or {}).get("base_url") or settings.AI_BASE_URL or "https://api.openai.com/v1"
        base_url = raw_url.split("/chat/completions")[0].split("/embeddings")[0].rstrip("/")
        if "/v1" not in base_url and "api.openai.com" not in base_url:
            base_url = f"{base_url}/v1"

        # Resolve embedding model dynamically via gateway
        embedding_model = EMBEDDING_MODEL
        try:
            gw_api_key, gw_base_url, gw_model = await self._get_embedding_config(org_id or "default")
            if gw_model:
                embedding_model = gw_model
            if gw_api_key:
                api_key = gw_api_key
            if gw_base_url:
                base_url = gw_base_url.rstrip("/")
                if "/v1" not in base_url and "api.openai.com" not in base_url:
                    base_url = f"{base_url}/v1"
        except Exception:
            pass

        if not api_key:
            logger.warning("VectorService: Missing AI Key.")
            if settings.IS_PRODUCTION:
                return "AI 检索服务暂不可用（API Key 未配置），请联系管理员。"
            return self._search_mock(query)

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/") + ("/v1" if "/v1" not in base_url else ""),
            timeout=_OPENAI_TIMEOUT,
        )

        try:
            return await self._search_supabase(
                query, user_id, limit, client, org_id=org_id, embedding_model=embedding_model
            )
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            if settings.IS_PRODUCTION:
                return f"知识库检索失败，请稍后重试。如果问题持续，请联系管理员。（错误: {str(e)[:80]}）"
            return self._search_mock(query)

    async def _search_supabase(
        self,
        query: str,
        user_id: str,
        limit: int,
        client: AsyncOpenAI,
        filters: dict[str, Any] = None,
        org_id: str = None,
        embedding_model: str = None,
    ) -> str:
        """
        Implementation for Hybrid Search (Vector + Keyword) with RRF.

        P0 Security: All searches are scoped to org_id to prevent cross-tenant leakage.
        """
        import asyncio

        _embedding_model = embedding_model or EMBEDDING_MODEL

        async def run_vector_search():
            try:
                response = await client.embeddings.create(input=query, model=_embedding_model, dimensions=_EMBEDDING_DIMENSIONS)
                embedding = response.data[0].embedding
                params = {
                    "query_embedding": embedding,
                    "match_threshold": 0.4,
                    "match_count": limit,
                    "filter": filters or {},
                    "p_user_id": user_id,
                    "p_org_id": org_id,
                }
                res = await supabase.rpc("match_documents", params).execute()
                return res.data or []
            except Exception as e:
                logger.error(f"Vector RPC failed: {e}")
                return []

        async def run_keyword_search():
            try:
                try:
                    res = await supabase.rpc(
                        "match_documents_keyword",
                        {
                            "p_query": query,
                            "p_user_id": user_id,
                            "p_limit": limit,
                            "p_org_id": org_id,  # P0: Always pass org_id
                        },
                    ).execute()
                    return res.data or []
                except Exception as rpc_err:
                    logger.debug(f"Keyword search RPC not available, falling back: {rpc_err}")

                # P0 Security: Fallback query also respects org_id
                base_query = supabase.table("document_embeddings").select("*, documents!inner(*)")

                # Always filter by user_id for security
                base_query = base_query.eq("documents.owner_id", user_id)

                # P0: If org_id is provided, add org-level filtering
                if org_id:
                    base_query = base_query.eq("documents.organization_id", org_id)

                res = await base_query.limit(limit).execute()

                flattened = []
                for item in res.data or []:
                    doc_data = item.pop("documents", {})
                    flattened.append(
                        {
                            **item,
                            "doc_metadata": doc_data.get("metadata"),
                            "doc_type": doc_data.get("doc_type"),
                        }
                    )
                return flattened
            except Exception as e:
                logger.warning(f"Keyword search failed completely: {e}")
                return []

        vector_res, keyword_res = await asyncio.gather(run_vector_search(), run_keyword_search())

        # Graceful degradation
        if not vector_res and keyword_res:
            logger.info("Vector search returned empty, using keyword results only")
            top_docs = keyword_res[:limit]
            if not top_docs:
                return f"知识库中未找到与 '{query}' 相关的公开或个人信息。建议您可以尝试更换关键词，或者上传相关文档后再试。"
            results = []
            for item in top_docs:
                content = item.get("content", "").strip()
                meta = item.get("metadata") or item.get("doc_metadata") or {}
                source = meta.get("source") or meta.get("file_name") or "公司知识库"
                type_label = self._get_doc_type_label(item)
                prefix = f"[{type_label}] " if type_label else ""
                results.append(f"{prefix}{content} [来源: {source}]")
            return "为您检索到以下相关企业知识 (关键词匹配):\n\n- " + "\n- ".join(results)

        # RRF Fusion
        fused_docs = self._rrf_fusion([vector_res, keyword_res], k=60)
        top_docs_unsorted = sorted(fused_docs.values(), key=lambda x: x["score"], reverse=True)[: limit * 2]

        # Reranking (if enabled and enough documents)
        # Item 42: Use unified RerankerService with cohere/bge/llm backends
        if settings.RERANK_ENABLED and len(top_docs_unsorted) > 1:
            rerank_top_n = settings.RERANK_TOP_N
            try:
                from app.services.reranker_service import reranker_service

                result = await reranker_service.rerank(query, top_docs_unsorted, top_k=rerank_top_n)
                top_docs = result.documents
                logger.info(
                    f"Reranked {len(top_docs_unsorted)} docs to {len(top_docs)} "
                    f"via {result.backend_used} in {result.latency_ms:.0f}ms"
                )
            except Exception as e:
                logger.warning(f"RerankerService failed, using RRF scores: {e}")
                top_docs = top_docs_unsorted[:limit]
        else:
            top_docs = top_docs_unsorted[:limit]

        if not top_docs:
            return (
                f"知识库中未找到与 '{query}' 相关的公开或个人信息。建议您可以尝试更换关键词，或者上传相关文档后再试。"
            )

        results = []
        # P2: Parent-document retriever — batch-fetch parent chunks to avoid N+1 queries
        parent_id_set = {
            item.get("parent_chunk_id")
            for item in top_docs
            if item.get("parent_chunk_id")
        }
        parent_content_map: dict[str, str] = {}
        if parent_id_set:
            try:
                parent_res = (
                    await supabase.table("document_embeddings")
                    .select("id, content")
                    .in_("id", list(parent_id_set))
                    .execute()
                )
                if parent_res.data:
                    for row in parent_res.data:
                        parent_content_map[str(row["id"])] = row.get("content", "").strip()
            except Exception as e:
                logger.debug(f"Batch parent chunk lookup failed: {e}")

        for item in top_docs:
            content = item.get("content", "").strip()

            # P2: Parent-document retriever — expand to parent chunk if available
            parent_id = item.get("parent_chunk_id")
            if parent_id and str(parent_id) in parent_content_map:
                parent_content = parent_content_map[str(parent_id)]
                if parent_content:
                    content = parent_content

            meta = item.get("metadata") or item.get("doc_metadata") or {}
            source = meta.get("source") or meta.get("file_name") or "公司知识库"
            type_label = self._get_doc_type_label(item)
            prefix = f"[{type_label}] " if type_label else ""
            results.append(f"{prefix}{content} [来源: {source}] (相似度: {item['score']:.4f})")

        return "为您检索到以下相关企业知识:\n\n- " + "\n- ".join(results)

    def _rrf_fusion(self, result_sets: list[list[Any]], k: int = 60) -> dict[any, dict]:
        """Reciprocal Rank Fusion"""
        fused = {}
        for rank_list in result_sets:
            for rank, item in enumerate(rank_list):
                doc_id = item["id"]
                if doc_id not in fused:
                    fused[doc_id] = {**item, "score": 0}
                fused[doc_id]["score"] += 1 / (k + rank + 1)
        return fused

    def _search_mock(self, query: str) -> str:
        """
        Mock data fallback.
        WARNING: Only used in development. Production should never reach here.
        """
        mock_data = [
            {
                "content": "主要销售流程: 线索 -> 初步沟通 -> 需求分析 -> 方案报价 -> 合同签订",
                "tags": ["流程", "销售"],
            },
            {
                "content": "差旅报销规定: 单日住宿不超过 800元，一线城市不超过 1200元。",
                "tags": ["财务", "报销"],
            },
            {
                "content": "公司根据年度绩效发放年终奖，S级员工可获得 3-6 个月薪资。",
                "tags": ["绩效", "人事"],
            },
        ]

        results = []
        for item in mock_data:
            if (
                any(k in query.lower() for k in [t.lower() for t in item["tags"]])
                or query.lower() in item["content"].lower()
            ):
                results.append(f"{item['content']} [来源: 模拟数据]")

        return (
            "为您检索到以下相关知识 (Mock):\n- " + "\n- ".join(results) if results else "知识库中未找到相关信息 (Mock)."
        )

    async def embed_text(self, text: str, org_id: str = "default") -> list[float] | None:
        """Generate an embedding vector for a single text string.

        Used by ConversationMemoryService for memory embeddings.
        Returns None on failure so callers can gracefully degrade.
        Uses in-process LRU cache to avoid redundant API calls.
        """
        if not text or not text.strip():
            return None

        # Cache lookup by content hash
        truncated = text.strip()[:8000]
        cache_key = hashlib.md5(truncated.encode()).hexdigest()
        if cache_key in self._embed_cache:
            embedding, ts = self._embed_cache[cache_key]
            if time.time() - ts < self._EMBED_CACHE_TTL:
                self._embed_cache.move_to_end(cache_key)
                return embedding
            else:
                del self._embed_cache[cache_key]  # expired

        try:
            api_key, base_url, model = await self._get_embedding_config(org_id)
            if not api_key:
                api_key = settings.OPENAI_API_KEY
            if not api_key:
                return None

            if not base_url:
                base_url = getattr(settings, "AI_BASE_URL", "https://api.openai.com/v1")
            base_url = base_url.rstrip("/")
            if "/v1" not in base_url and "api.openai.com" not in base_url:
                base_url = f"{base_url}/v1"

            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            response = await client.embeddings.create(
                input=truncated,
                model=model or _DEFAULT_EMBEDDING_MODEL,
                dimensions=_EMBEDDING_DIMENSIONS,
            )
            embedding = response.data[0].embedding

            # Cache the result (LRU eviction with TTL)
            self._embed_cache[cache_key] = (embedding, time.time())
            if len(self._embed_cache) > self._EMBED_CACHE_MAX:
                self._embed_cache.popitem(last=False)

            return embedding
        except Exception as e:
            logger.warning(f"Failed to generate embedding: {e}")
            return None

    # Keep backward-compatible private alias
    _embed_text = embed_text

    async def check_staleness(self, org_id: str, staleness_days: int = 30, db=None) -> list[dict]:
        """
        #25 Knowledge Base Update Strategy: Check which documents have stale embeddings.
        Returns list of documents whose embeddings are older than staleness_days.
        """
        client = db or supabase
        if not client:
            return []

        cutoff = (datetime.utcnow() - timedelta(days=staleness_days)).isoformat()
        try:
            res = (
                await client.table("documents")
                .select("id, name, updated_at, last_embedded_at")
                .eq("organization_id", org_id)
                .execute()
            )

            stale = []
            for doc in res.data or []:
                last_embedded = doc.get("last_embedded_at")
                updated_at = doc.get("updated_at")
                if not last_embedded or last_embedded < cutoff:
                    stale.append(
                        {
                            "document_id": doc["id"],
                            "name": doc.get("name"),
                            "updated_at": updated_at,
                            "last_embedded_at": last_embedded,
                            "reason": "never_embedded" if not last_embedded else "stale",
                        }
                    )
                elif updated_at and last_embedded and updated_at > last_embedded:
                    stale.append(
                        {
                            "document_id": doc["id"],
                            "name": doc.get("name"),
                            "updated_at": updated_at,
                            "last_embedded_at": last_embedded,
                            "reason": "modified_after_embedding",
                        }
                    )
            return stale
        except Exception as e:
            logger.error(f"Staleness check failed: {e}")
            return []

    async def incremental_update(
        self,
        document_id: str,
        chunks: list[str],
        org_id: str,
        config: dict = None,
        db=None,
        expires_at: str | None = None,
    ) -> dict:
        """
        #25 Knowledge Base Update Strategy: Incrementally update embeddings.
        Only re-embeds chunks that have changed (by content hash diff).
        Cleans up orphan chunks that no longer exist.
        """
        client = db or supabase
        if not client:
            return {"status": "error", "reason": "no_db"}

        api_key = (config or {}).get("api_key") or settings.OPENAI_API_KEY
        if not api_key:
            return {"status": "error", "reason": "no_api_key"}

        # Resolve embedding model dynamically
        embedding_model = EMBEDDING_MODEL
        try:
            gw_api_key, _gw_base_url, gw_model = await self._get_embedding_config(org_id or "default")
            if gw_model:
                embedding_model = gw_model
            if gw_api_key:
                api_key = gw_api_key
        except Exception:
            pass

        oai_client = AsyncOpenAI(api_key=api_key)
        stats = {"inserted": 0, "updated": 0, "deleted": 0, "unchanged": 0}

        try:
            # 1. Load existing chunks
            existing_res = (
                await client.table("document_embeddings")
                .select("id, chunk_index, content_hash")
                .eq("document_id", document_id)
                .execute()
            )

            existing_map = {}
            for row in existing_res.data or []:
                existing_map[row["chunk_index"]] = {
                    "id": row["id"],
                    "content_hash": row.get("content_hash"),
                }

            # 2. Compute hashes for new chunks
            new_chunk_hashes = {}
            for i, chunk in enumerate(chunks):
                new_chunk_hashes[i] = hashlib.sha256(chunk.encode()).hexdigest()

            # 3. Determine what needs updating
            to_embed = []
            for i, chunk in enumerate(chunks):
                existing = existing_map.get(i)
                if not existing or existing.get("content_hash") != new_chunk_hashes[i]:
                    to_embed.append((i, chunk))
                else:
                    stats["unchanged"] += 1

            # 4. Embed changed chunks
            if to_embed:
                texts = [t[1] for t in to_embed]
                response = await oai_client.embeddings.create(input=texts, model=embedding_model, dimensions=_EMBEDDING_DIMENSIONS)
                for idx, (chunk_index, chunk_text) in enumerate(to_embed):
                    embedding = response.data[idx].embedding
                    row_data = {
                        "document_id": document_id,
                        "chunk_index": chunk_index,
                        "content": chunk_text,
                        "content_hash": new_chunk_hashes[chunk_index],
                        "embedding": embedding,
                        "organization_id": org_id,
                        "embedding_model": embedding_model,
                        "embedding_model_version": EMBEDDING_MODEL_VERSION,
                    }
                    if expires_at is not None:
                        row_data["expires_at"] = expires_at
                    if chunk_index in existing_map:
                        await (
                            client.table("document_embeddings")
                            .update(row_data)
                            .eq("id", existing_map[chunk_index]["id"])
                            .execute()
                        )
                        stats["updated"] += 1
                    else:
                        await client.table("document_embeddings").insert(row_data).execute()
                        stats["inserted"] += 1

            # 5. Delete orphan chunks (indices that no longer exist)
            for old_index, old_data in existing_map.items():
                if old_index >= len(chunks):
                    try:
                        await client.table("document_embeddings").delete().eq("id", old_data["id"]).execute()
                    except Exception as del_e:
                        if not (hasattr(del_e, "code") and str(getattr(del_e, "code", "")) == "204"):
                            raise
                    stats["deleted"] += 1

            # 6. Update last_embedded_at on the document
            await (
                client.table("documents")
                .update({"last_embedded_at": datetime.utcnow().isoformat()})
                .eq("id", document_id)
                .execute()
            )

            return {"status": "ok", **stats}
        except Exception as e:
            logger.error(f"Incremental update failed for {document_id}: {e}")
            return {"status": "error", "reason": str(e)}


# Singleton instance
vector_service = VectorService()
