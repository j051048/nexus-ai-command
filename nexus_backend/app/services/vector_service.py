import os
from typing import List, Dict, Any
from app.core.database import supabase
from app.core.config import settings
from openai import AsyncOpenAI

class VectorService:
    """
    Interface for Vector Database operations using Supabase pgvector.
    Transitioned from Mock to Real Implementation (Week 1 Goal).
    """

    async def search(self, query: str, limit: int = 3, config: dict = None) -> str:
        """
        Semantic search in the vector DB.
        Returns a formatted string of results.
        """
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
            return await self._search_supabase(query, limit, client)
        except Exception as e:
            print(f"Vector search failed: {e}")
            return self._search_mock(query)

    async def _search_supabase(self, query: str, limit: int, client: AsyncOpenAI) -> str:
        """
        Implementation for Hybrid Search (Vector + Keyword) with RRF.
        P0 Optimization: Fixes "ID search" failure cases.
        """
        import asyncio
        
        # A. Vector Search (Semantic)
        async def run_vector_search():
             try:
                 response = await client.embeddings.create(input=query, model="text-embedding-3-small")
                 embedding = response.data[0].embedding
                 params = {"query_embedding": embedding, "match_threshold": 0.5, "match_count": limit}
                 return supabase.rpc("match_documents", params).execute().data or []
             except Exception: return []

        # B. Keyword Search (Lexical) - using Postgres Full Text Search (P1 Optimization)
        # Note: Requires 'fts' generated column and GIN index (see migration 20240201)
        async def run_keyword_search():
             try:
                 # Use 'websearch_to_tsquery' logic via Supabase .textSearch()
                 # 'plain' config maps to 'common' dictionary usually, or we specify config='simple' if possible
                 # Supabase-py textSearch syntax: .textSearch('fts', query, config='simple')
                 return supabase.table("document_embeddings").select("*").textSearch("fts", query, config="simple").limit(limit).execute().data or []
             except Exception as e: 
                 # Fallback to ILIKE if FTS fails (e.g. migration not run)
                 print(f"FTS failed, fallback to ilike: {e}")
                 return supabase.table("document_embeddings").select("*").ilike("content", f"%{query}%").limit(limit).execute().data or []

        # Run Parallel
        vector_res, keyword_res = await asyncio.gather(run_vector_search(), run_keyword_search())
        
        # C. RRF Fusion
        fused_docs = self._rrf_fusion([vector_res, keyword_res], k=60)
        top_docs = sorted(fused_docs.values(), key=lambda x: x['score'], reverse=True)[:limit]

        if not top_docs:
            return "知识库中未找到相关信息 (No relevant documents found in Vector DB)."

        # 3. Format results
        results = []
        for item in top_docs:
            content = item.get("content", "")
            meta = item.get("metadata", {}) or {}
            source = meta.get("filename", "未知来源")
            
            # Grounding: Append citation marker
            citation = f" [引用溯源: {source}]"
            results.append(f"{content}...{citation} (混合匹配)")

        return "检索到以下相关知识:\n" + "\n- ".join(results)

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
