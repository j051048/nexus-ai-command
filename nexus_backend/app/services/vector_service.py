import os
from typing import List, Dict, Any

class VectorService:
    """
    Abstact interface for Vector Database operations.
    Currently implements a Mock/Placeholder.
    Future integration with Milvus should be implemented here.
    """

    def __init__(self):
        self.provider = os.getenv("VECTOR_STORE_PROVIDER", "mock") # mock or milvus
        self.milvus_uri = os.getenv("MILVUS_URI", "http://localhost:19530")
        self.milvus_token = os.getenv("MILVUS_TOKEN", "")
        self.collection_name = "nexus_knowledge"
        
        # Check if we should initialize real connection
        if self.provider == "milvus":
            self._connect_milvus()

    def _connect_milvus(self):
        """
        Placeholder for Milvus connection logic.
        Requires verify: pip install pymilvus
        """
        try:
            # from pymilvus import connections, Collection
            # connections.connect(uri=self.milvus_uri, token=self.milvus_token)
            print(f"Would connect to Milvus at {self.milvus_uri}")
            pass
        except Exception as e:
            print(f"Failed to connect to Milvus: {e}")

    async def search(self, query: str, limit: int = 3) -> str:
        """
        Semantic search in the vector DB.
        Returns a formatted string of results.
        """
        if self.provider == "milvus":
            return await self._search_milvus(query, limit)
        else:
            return self._search_mock(query)

    async def _search_milvus(self, query: str, limit: int) -> str:
        """
        Actual implementation for Milvus search.
        TODO: Uncomment and refinements when Milvus is deployed.
        """
        # 1. Convert query to vector (using OpenAI embedding or local model)
        # 2. search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
        # 3. results = collection.search(vectors=[vec], anns_field="embedding", param=search_params, limit=limit)
        # 4. Format results
        return f"[Milvus] 尚未连接真实数据库。请检查环境变量配置。搜索词: {query}"

    def _search_mock(self, query: str) -> str:
        """
        Mock data for demonstration until real DB is ready.
        """
        # Simple keyword matching for demo
        mock_data = [
            {"content": "主要销售流程: 线索 -> 初步沟通 -> 需求分析 -> 方案报价 -> 合同签订", "tags": ["流程", "销售"]},
            {"content": "差旅报销规定: 单日住宿不超过 800元，一线城市不超过 1200元。", "tags": ["财务", "报销"]},
            {"content": "公司根据年度绩效发放年终奖，S级员工可获得 3-6 个月薪资。", "tags": ["绩效", "人事"]}
        ]
        
        results = []
        for item in mock_data:
            if any(k in query for k in item["tags"]) or query in item["content"]:
                results.append(item["content"])
        
        if not results:
            return "知识库中未找到相关信息 (当前为 Mock 模式)。"
        
        return "检索到以下相关知识:\n" + "\n- ".join(results)

# Singleton instance
vector_service = VectorService()
