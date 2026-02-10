import os
import re
import logging
from typing import List, Dict, Any
from app.core.database import supabase
from app.core.config import settings
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


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
                 # We need to fetch the user's department first for cross-department checks
                 v_dept = None
                 u_res = await supabase.table("users").select("department").eq("id", user_id).maybe_single().execute()
                 if u_res.data:
                     v_dept = u_res.data.get("department")

                 # P0 Security Fix #4: Use OR logical filter for visibility
                 # organization OR (department=v_dept) OR (owner_id=user_id)
                 visibility_filter = f"visibility.eq.organization,and(visibility.eq.department,department.eq.{v_dept})"
                 if user_id:
                     visibility_filter += f",owner_id.eq.{user_id}"
                 
                 # Using the !inner join syntax to filter based on related documents table
                 # Note: PostgREST OR logic can be complex with joins. 
                 # Safer implementation: Use match_documents_keyword RPC if available, 
                 # or fetch with filter.
                 
                 query_builder = supabase.table("document_embeddings").select("*, documents!inner(*)").text_search("fts", query, config="simple")
                 
                 # Visibility logic via PostgREST horizontal filtering
                 # (visibility='organization' OR (visibility='department' AND department=D) OR owner_id=U)
                 # Note: documents!inner(*) allows access to document columns
                 
                 # For simplicity and correctness with the complex OR logic + Join, 
                 # it is better to use a dedicated keyword search RPC that mirrors match_documents logic
                 # but uses FTS.
                 
                 # Fallback to a simpler owner_id filter for now if RPC not ready, 
                 # but the goal is org-wide. Let's try the complex filter.
                 
                 res = await query_builder\
                    .or_(f"visibility.eq.organization,and(visibility.eq.department,department.eq.{v_dept}),owner_id.eq.{user_id}", foreign_table="documents")\
                    .limit(limit).execute()
                 
                 # Flatten the results to match vector search structure
                 flattened = []
                 for item in (res.data or []):
                     doc_data = item.pop("documents", {})
                     # Merge document-level visibility/metadata if needed
                     flattened.append({**item, "doc_metadata": doc_data.get("metadata")})
                 
                 return flattened
             except Exception as e: 
                 # Fallback to ILIKE if FTS fails
                 print(f"Keyword search failed: {e}")
                 # For security and simplicity, fallback results should at least be private
                 res = await supabase.table("document_embeddings").select("*, documents!inner(*)").eq("documents.owner_id", user_id).limit(limit).execute()
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
