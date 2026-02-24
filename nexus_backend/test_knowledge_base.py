import asyncio
import os
import sys

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.etl_service import etl_service
from app.services.vector_service import vector_service


async def test_knowledge_base():
    print("=== Testing Knowledge Base Deployment ===")

    # 1. Define sample enterprise product data (as if uploaded)
    sample_product_doc = """
    【核心产品手册】Nexus AI Command 中控系统
    版本：V2.5
    核心功能：
    - 多Agent协同：支持销售指挥官、审批管家、绩效教练三种角色智能体。
    - 知识库RAG：支持PDF/Word文档上传，基于Supabase pgvector实现毫秒级检索。
    - 全域互联：已打通钉钉、企业微信、Kingdee金蝶ERP。

    技术规格：
    - 后端：FastAPI + Python 3.10
    - Vector DB: Supabase (PostgreSQL 17 + pgvector)
    - LLM: OpenAI GPT-4o / DeepSeek V3

    部署要求：
    - 内存：最低 4GB
    - 容器化支持：Docker / Kubernetes
    """

    filename = "product_manual_v2.5.txt"
    print(f"\n[1] Simulating file upload: {filename}")

    # Mock OpenAI if missing (Connectivity Test)
    if not etl_service.openai_client:
        print("⚠️ OpenAI API Key not found. Using MOCK Embeddings for Connectivity Test.")

        class MockEmbeddingResponse:
            def __init__(self):
                self.data = [type("obj", (object,), {"embedding": [0.1] * 1536})()]

        class MockEmbeddings:
            def create(self, input, model):
                return MockEmbeddingResponse()

        class MockClient:
            def __init__(self):
                self.embeddings = MockEmbeddings()
                self.chat = None

        etl_service.openai_client = MockClient()
        vector_service.openai_client = MockClient()

    # 2. Ingest Data (ETL)
    try:
        # Mocking OpenAI chat completion for extraction test
        if not etl_service.openai_client.chat:

            class MockChat:
                def __init__(self):
                    self.completions = self

                def create(self, **kwargs):
                    class MockChoice:
                        message = type("obj", (object,), {"content": '{"doc_type": "manual"}'})()

                    return type("obj", (object,), {"choices": [MockChoice()]})()

            etl_service.openai_client.chat = MockChat()

        success = await etl_service.process_text_with_extraction(sample_product_doc, filename, len(sample_product_doc))
        if success:
            print("✅ ETL Success: Document chunked and embedded.")
        else:
            print("❌ ETL Failed.")
            return
    except Exception as e:
        print(f"❌ ETL Exception: {e}")
        return

    # 3. Test Search (Retrieval)
    query = "Nexus AI 支持哪些ERP系统？"
    print(f"\n[2] Testing Retrieval Query: '{query}'")

    try:
        results = await vector_service.search(query)
        print("\n--- Search Results ---")
        print(results)
        print("----------------------")

        if "Kingdee" in results or "金蝶" in results:
            print("\n✅ Verification PASSED: Knowledge base is active and retrieving correctly.")
        else:
            print("\n⚠️ Verification WARNING: Content mismatch or embedding delay.")

    except Exception as e:
        print(f"❌ Search Exception: {e}")


if __name__ == "__main__":
    asyncio.run(test_knowledge_base())
