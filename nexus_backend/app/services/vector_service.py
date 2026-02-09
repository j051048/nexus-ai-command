import os
import re
from typing import List, Dict, Any
from app.core.database import supabase
from app.core.config import settings
from openai import AsyncOpenAI


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
            print("VectorService: Missing AI Key.")
            return self._search_mock(query)

        # Initialize client per search to ensure correct proxy/key
        client = AsyncOpenAI(api_key=api_key, base_url=base_url.rstrip("/") + ("/v1" if "/v1" not in base_url else ""))
        
        try:
            return await self._search_supabase(query, user_id, limit, client)
        except Exception as e:
            print(f"Vector search failed: {e}")
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

        # B. Keyword Search (Lexical) - Filter by owner_id in the documents table
        async def run_keyword_search():
             try:
                 # Use inner join-like filter on documents owner_id
                 query_builder = supabase.table("document_embeddings").select("*, documents!inner(owner_id)").eq("documents.owner_id", user_id).text_search("fts", query, config="simple")
                 
                 # Apply Metadata Filters for Keyword Search
                 if filters:
                     query_builder = query_builder.contains("metadata", filters)
                 
                 res = await query_builder.limit(limit).execute()
                 return res.data or []
             except Exception as e: 
                                  # Fallback to ILIKE with relationship filter
                 # P0 Security: Escape LIKE pattern to prevent injection
                 print(f"FTS failed, fallback to ilike: {e}")
                 escaped_query = escape_like_pattern(query)
                 base = supabase.table("document_embeddings").select("*, documents!inner(owner_id)").eq("documents.owner_id", user_id).ilike("content", f"%{escaped_query}%")
                 if filters:
                     base = base.contains("metadata", filters)
                 res = await base.limit(limit).execute()
                 return res.data or []

        # Run Parallel
        vector_res, keyword_res = await asyncio.gather(run_vector_search(), run_keyword_search())
        
        # C. RRF Fusion
        fused_docs = self._rrf_fusion([vector_res, keyword_res], k=60)
        top_docs = sorted(fused_docs.values(), key=lambda x: x['score'], reverse=True)[:limit]

        if not top_docs:
            # TC-07: Better empty result handling
            return f"知识库中未找到与 '{query}' 相关的公开或个人信息。建议您可以尝试更换关键词，或者上传相关文档后再试。"

        # 3. Format results
        results = []
        for item in top_docs:
            content = item.get("content", "").strip()
            meta = item.get("metadata", {}) or {}
            source = meta.get("source", "未知来源") # etl_service uses 'source'
            
            # Grounding: Append citation marker (TC-04)
            citation = f" [资料来源: {source}]"
            results.append(f"{content}...{citation} (混合匹配权重: {item['score']:.4f})")

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
        """
        mock_data = [
            {"content": "主要销售流程: 线索 -> 初步沟通 -> 需求分析 -> 方案报价 -> 合同签订", "tags": ["流程", "销售"]},
            {"content": "差旅报销规定: 单日住宿不超过 800元，一线城市不超过 1200元。", "tags": ["财务", "报销"]},
            {"content": "公司根据年度绩效发放年终奖，S级员工可获得 3-6 个月薪资。", "tags": ["绩效", "人事"]}
        ]
        
        results = []
        for item in mock_data:
            if any(k in query for k in item["tags"]) or query in item["content"]:
                results.append(item["content"])
        
        return "检索到以下相关知识 (Mock):\n" + "\n- ".join(results) if results else "知识库中未找到相关信息 (Mock)."

# Singleton instance
vector_service = VectorService()
