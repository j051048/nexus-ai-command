import re
import logging
from typing import List, Dict, Any, Optional
from app.core.database import supabase
from app.core.config import settings
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Reranker configuration
RERANK_ENABLED = getattr(settings, 'RERANK_ENABLED', True)
RERANK_TOP_N = getattr(settings, 'RERANK_TOP_N', 5)


def escape_like_pattern(value: str) -> str:
    """P0 Security: Escape special characters in LIKE patterns to prevent SQL injection"""
    if not value:
        return value
    # Escape %, _, and \ which have special meaning in LIKE patterns
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def sanitize_search_query(query: str, max_length: int = 500) -> str:
    """P0 Security: Sanitize and validate search query input"""
    if not query:
        return ""
    # Truncate to max length
    query = query[:max_length]
    # Remove potential injection patterns
    query = re.sub(r'[;\-\-\'"\\]', ' ', query)
    # Normalize whitespace
    query = ' '.join(query.split())
    return query.strip()


class VectorService:
    """
    Interface for Vector Database operations using Supabase pgvector.
    Enhanced with Cross-Encoder Reranking for improved precision.
    """

    async def _rerank_with_llm(
        self,
        query: str,
        documents: List[Dict],
        client: AsyncOpenAI,
        top_n: int = 5
    ) -> List[Dict]:
        """
        Use LLM to rerank documents based on relevance to query.
        This is a lightweight cross-encoder alternative using GPT.
        """
        if not documents or len(documents) <= 1:
            return documents

        try:
            # Prepare document list for reranking
            doc_texts = []
            for i, doc in enumerate(documents[:10]):  # Limit to top 10 for reranking
                content = doc.get("content", "")[:500]  # Truncate long content
                doc_texts.append(f"[{i}] {content}")

            prompt = f"""对以下文档按照与查询的相关性进行排序。
查询: {query}

文档列表:
{chr(10).join(doc_texts)}

请直接返回排序后的文档编号（用逗号分隔），最相关的排在前面。只返回编号，例如: 2,0,4,1,3"""

            response = await client.chat.completions.create(
                model="gpt-4o-mini",  # Use fast model for reranking
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0
            )

            # Parse response
            ranking_str = response.choices[0].message.content.strip()
            # Extract numbers from response
            indices = []
            for part in ranking_str.replace(" ", "").split(","):
                try:
                    idx = int(part.strip("[]"))
                    if 0 <= idx < len(documents):
                        indices.append(idx)
                except ValueError:
                    continue

            # Reorder documents based on LLM ranking
            if indices:
                reranked = []
                seen = set()
                for idx in indices[:top_n]:
                    if idx not in seen:
                        reranked.append(documents[idx])
                        seen.add(idx)
                # Add any remaining documents not in the ranking
                for i, doc in enumerate(documents):
                    if i not in seen and len(reranked) < top_n:
                        reranked.append(doc)
                return reranked

        except Exception as e:
            logger.warning(f"LLM reranking failed, using RRF scores: {e}")

        return documents[:top_n]


def escape_like_pattern(value: str) -> str:
    """P0 Security: Escape special characters in LIKE patterns to prevent SQL injection"""
    if not value:
        return value
    # Escape %, _, and \ which have special meaning in LIKE patterns
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def sanitize_search_query(query: str, max_length: int = 500) -> str:
    """P0 Security: Sanitize and validate search query input"""
    if not query:
        return ""
    # Truncate to max length
    query = query[:max_length]
    # Remove potential injection patterns
    query = re.sub(r'[;\-\-\'"\\]', ' ', query)
    # Normalize whitespace
    query = ' '.join(query.split())
    return query.strip()

class VectorService:
    """
    Interface for Vector Database operations using Supabase pgvector.
    Transitioned from Mock to Real Implementation (Week 1 Goal).
    """

    async def search(self, query: str, user_id: str, limit: int = 3, config: dict = None) -> str:
        """
        Semantic search in the vector DB.
        Returns a formatted string of results.
        """
        # P0 Security: Sanitize input query
        query = sanitize_search_query(query)
        if not query:
            return "请提供有效的搜索关键词。"
        
        # P0 Security: Validate limit parameter
        limit = min(max(1, limit), 10)  # Clamp between 1 and 10
        # use dynamic config or default settings
        api_key = (config or {}).get("api_key") or settings.OPENAI_API_KEY
        
        # URL Normalization
        raw_url = (config or {}).get("base_url") or settings.AI_BASE_URL or "https://api.openai.com/v1"
        base_url = raw_url.split("/chat/completions")[0].split("/embeddings")[0].rstrip("/")
        if "/v1" not in base_url and "api.openai.com" not in base_url:
            base_url = f"{base_url}/v1"
        
        if not api_key:
            logger.warning("VectorService: Missing AI Key.")
            if settings.IS_PRODUCTION:
                return "AI 检索服务暂不可用（API Key 未配置），请联系管理员。"
            return self._search_mock(query)

        # Initialize client per search to ensure correct proxy/key
        client = AsyncOpenAI(api_key=api_key, base_url=base_url.rstrip("/") + ("/v1" if "/v1" not in base_url else ""))
        
        try:
            return await self._search_supabase(query, user_id, limit, client)
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            if settings.IS_PRODUCTION:
                return f"知识库检索失败，请稍后重试。如果问题持续，请联系管理员。（错误: {str(e)[:80]}）"
            return self._search_mock(query)

    async def _search_supabase(self, query: str, user_id: str, limit: int, client: AsyncOpenAI, filters: Dict[str, Any] = None) -> str:
        """
        Implementation for Hybrid Search (Vector + Keyword) with RRF.
        Supports mandatory user_id isolation.
        """
        import asyncio
        
        # A. Vector Search (Semantic) - P0 Security Fix #4: Restored user_id for visibility control
        async def run_vector_search():
             try:
                 response = await client.embeddings.create(input=query, model="text-embedding-3-small")
                 embedding = response.data[0].embedding
                 params = {
                     "query_embedding": embedding, 
                     "match_threshold": 0.4, 
                     "match_count": limit,
                     # P0 Security Fix #4: Restored! Uses three-tier visibility model
                     # (private/department/organization) instead of strict user isolation
                     "p_user_id": user_id
                 }
                 if filters:
                     params["filter"] = filters
                 res = await supabase.rpc("match_documents", params).execute()
                 return res.data or []
             except Exception as e:
                 print(f"Vector RPC failed: {e}")
                 return []

        # B. Keyword Search (Lexical) - Respect Three-Tier Visibility Model
        async def run_keyword_search():
            try:
                # Try RPC-based keyword search first (handles visibility correctly)
                try:
                    res = await supabase.rpc("match_documents_keyword", {
                        "p_query": query,
                        "p_user_id": user_id,
                        "p_limit": limit
                    }).execute()
                    return res.data or []
                except Exception as rpc_err:
                    logger.debug(f"Keyword search RPC not available, falling back: {rpc_err}")
                
                # Fallback: simple owner_id filter
                res = await supabase.table("document_embeddings")\
                    .select("*, documents!inner(*)")\
                    .eq("documents.owner_id", user_id)\
                    .limit(limit).execute()
                
                flattened = []
                for item in (res.data or []):
                    doc_data = item.pop("documents", {})
                    flattened.append({**item, "doc_metadata": doc_data.get("metadata")})
                return flattened
            except Exception as e:
                logger.warning(f"Keyword search failed completely: {e}")
                return []

        # Run Parallel
        vector_res, keyword_res = await asyncio.gather(run_vector_search(), run_keyword_search())
        
        # Graceful degradation: if one search path failed, use the other directly
        if not vector_res and keyword_res:
            logger.info("Vector search returned empty, using keyword results only")
            top_docs = keyword_res[:limit]
            # Format and return directly
            if not top_docs:
                return f"知识库中未找到与 '{query}' 相关的公开或个人信息。建议您可以尝试更换关键词，或者上传相关文档后再试。"
            results = []
            for item in top_docs:
                content = item.get("content", "").strip()
                meta = item.get("metadata") or item.get("doc_metadata") or {}
                source = meta.get("source") or meta.get("file_name") or "公司知识库"
                results.append(f"{content} [来源: {source}]")
            return "为您检索到以下相关企业知识 (关键词匹配):\n\n- " + "\n- ".join(results)
        
        # C. RRF Fusion
        fused_docs = self._rrf_fusion([vector_res, keyword_res], k=60)
        top_docs_unsorted = sorted(fused_docs.values(), key=lambda x: x['score'], reverse=True)[:limit * 2]

        # D. Reranking (if enabled and enough documents)
        if RERANK_ENABLED and len(top_docs_unsorted) > 1:
            try:
                top_docs = await self._rerank_with_llm(query, top_docs_unsorted, client, top_n=limit)
                logger.info(f"Reranked {len(top_docs_unsorted)} docs to {len(top_docs)}")
            except Exception as e:
                logger.warning(f"Reranking failed: {e}")
                top_docs = top_docs_unsorted[:limit]
        else:
            top_docs = top_docs_unsorted[:limit]

        if not top_docs:
            # TC-07: Better empty result handling
            return f"知识库中未找到与 '{query}' 相关的公开或个人信息。建议您可以尝试更换关键词，或者上传相关文档后再试。"

        # 3. Format results
        results = []
        for item in top_docs:
            content = item.get("content", "").strip()
            # Try to get metadata from embedding level or document level
            meta = item.get("metadata") or item.get("doc_metadata") or {}
            source = meta.get("source") or meta.get("file_name") or "公司知识库"
            
            # Grounding: Append citation marker (TC-04)
            results.append(f"{content} [来源: {source}] (相似度: {item['score']:.4f})")

        return "为您检索到以下相关企业知识:\n\n- " + "\n- ".join(results)

    def _rrf_fusion(self, result_sets: List[List[Any]], k: int = 60) -> Dict[any, Dict]:
        """Reciprocal Rank Fusion"""
        fused = {}
        for rank_list in result_sets:
            for rank, item in enumerate(rank_list):
                doc_id = item['id']
                if doc_id not in fused:
                    fused[doc_id] = {**item, 'score': 0}
                fused[doc_id]['score'] += 1 / (k + rank + 1)
        return fused

    def _search_mock(self, query: str) -> str:
        """
        Mock data fallback.
        WARNING: Only used in development. Production should never reach here.
        """
        mock_data = [
            {"content": "主要销售流程: 线索 -> 初步沟通 -> 需求分析 -> 方案报价 -> 合同签订", "tags": ["流程", "销售"]},
            {"content": "差旅报销规定: 单日住宿不超过 800元，一线城市不超过 1200元。", "tags": ["财务", "报销"]},
            {"content": "公司根据年度绩效发放年终奖，S级员工可获得 3-6 个月薪资。", "tags": ["绩效", "人事"]}
        ]
        
        results = []
        for item in mock_data:
            if any(k in query.lower() for k in [t.lower() for t in item["tags"]]) or query.lower() in item["content"].lower():
                results.append(f"{item['content']} [来源: 模拟数据]")
        
        return "为您检索到以下相关知识 (Mock):\n- " + "\n- ".join(results) if results else "知识库中未找到相关信息 (Mock)."

# Singleton instance
vector_service = VectorService()
