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

    def __init__(self):
        self.provider = "supabase"
        self.openai_client = None
        if settings.OPENAI_API_KEY:
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def search(self, query: str, limit: int = 3) -> str:
        """
        Semantic search in the vector DB.
        Returns a formatted string of results.
        """
        # Fallback to mock if dependencies are missing
        if not self.openai_client or not supabase:
            print("VectorService: Missing OpenAI Key or Supabase client. Falling back to Mock.")
            return self._search_mock(query)

        try:
            return await self._search_supabase(query, limit)
        except Exception as e:
            print(f"Vector search failed: {e}")
            return self._search_mock(query)

    async def _search_supabase(self, query: str, limit: int) -> str:
        """
        Implementation for Supabase pgvector search.
        """
        # 1. Convert query to vector
        try:
            response = await self.openai_client.embeddings.create(
                input=query,
                model="text-embedding-3-small"
            )
            embedding = response.data[0].embedding
        except Exception as e:
            print(f"Embedding generation failed: {e}")
            raise e

        # 2. RPC call to match_documents
        params = {
            "query_embedding": embedding,
            "match_threshold": 0.5, # Adjust threshold as needed
            "match_count": limit
        }
        
        try:
            rpc_response = supabase.rpc("match_documents", params).execute()
        except Exception as e:
            print(f"Supabase RPC failed: {e}")
            # Likely function not found if migration hasn't run.
            raise e
        
        if not rpc_response.data:
            return "知识库中未找到相关信息 (No relevant documents found in Vector DB)."

        # 3. Format results
        results = []
        for item in rpc_response.data:
            content = item.get("content", "")
            meta = item.get("metadata", {}) or {}
            source = meta.get("filename", "未知来源")
            sim = item.get("similarity", 0)
            results.append(f"[{source}] (匹配度 {sim:.2f}) {content}...")

        return "检索到以下相关知识:\n" + "\n- ".join(results)

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
