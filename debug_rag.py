
import asyncio
import os
import sys
import io

# Add project root to path
sys.path.append(os.getcwd())

from app.services.etl_service import etl_service
from app.services.vector_service import vector_service
from app.core.database import supabase
from fastapi import UploadFile

async def debug_rag():
    # User "建林" credentials from Supabase
    user_id = "6b90bb73-eff5-48af-84f3-513ef03a6227"
    api_key = "sk-izkpsk5SHgaCZbBmFfF2Cc64Ae7a42E28e9c31EeA5E734F0"
    base_url = "https://api.apiyi.com/v1/chat/completions" # Root cause: this has full path
    
    print(f"--- RAG Debug Start ---")
    print(f"User: 建林 ({user_id})")
    print(f"Proxy URL: {base_url}")
    
    # 1. Simulate File Upload
    file_content = """
    【智能中药材检测仪 ZY-100型】
    技术参数：
    - 水分测定范围：0.5% - 45% (精度 ±0.1%)
    - 总灰分检测时间：15分钟
    - 主要检测成分：人参皂苷、黄芪甲苷、大黄素。
    - 传感器类型：近红外光谱扫描仪 (NIR)
    - 运行环境：5°C - 40°C
    - 生产商：Nexus Health Technology
    """
    
    mock_file = UploadFile(
        filename="zy100_manual.txt",
        file=io.BytesIO(file_content.encode("utf-8"))
    )
    
    print("\n[Step 1] Processing file...")
    # This should now handle the URL correctly after my fix
    result = await etl_service.process_file(mock_file, api_key=api_key, base_url=base_url)
    print(f"Result: {result}")
    
    if result.get("status") != "success":
        print("FAIL: ETL Pipeline failed.")
        return

    doc_id = result.get("document_id")
    print(f"SUCCESS: Document {doc_id} created and embedded.")

    # 2. Simulate Search
    print("\n[Step 2] Testing Vector Search...")
    search_query = "中药材检测仪有哪些测量参数？"
    # Pass config as the front-end now does
    search_result = await vector_service.search(search_query, config={"api_key": api_key, "base_url": base_url})
    print(f"Search Result:\n{search_result}")

    if "测定范围" in search_result or "水分" in search_result:
        print("\n--- FINAL VERDICT: RAG IS WORKING ---")
    else:
        print("\n--- FINAL VERDICT: RETRIEVAL FAILED ---")

if __name__ == "__main__":
    asyncio.run(debug_rag())
