import os
import random
# from pymilvus import connections, Collection

class MilvusService:
    def __init__(self):
        self.host = os.getenv("MILVUS_HOST", "localhost")
        self.port = os.getenv("MILVUS_PORT", "19530")
        self.mock_mode = True # Default to mock for initial stability

    def connect(self):
        """
        Attempt to connect to Milvus. Fallback to mock if fails.
        """
        try:
            # connections.connect("default", host=self.host, port=self.port)
            # self.mock_mode = False
            # print("Connected to Milvus real instance.")
            print("Milvus connection mocked (uncomment code to use real DB)")
        except Exception as e:
            print(f"Milvus connection failed: {e}. Switching to Mock Mode.")
            self.mock_mode = True

    def search_similar_leads(self, text_description: str, limit=5):
        if self.mock_mode:
            return [
                {"id": str(i), "score": random.uniform(0.7, 0.99), "content": f"Mock Lead based on {text_description[:10]}..."} 
                for i in range(limit)
            ]
        else:
            # Real Milvus search logic would go here
            pass

    def index_call_transcript(self, transcript_id: str, text: str):
        if self.mock_mode:
            print(f"[Mock Milvus] Indexed transcript {transcript_id}")
        else:
            # Real embedding + insert logic
            pass

milvus_client = MilvusService()
