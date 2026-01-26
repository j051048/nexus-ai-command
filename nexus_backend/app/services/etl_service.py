from app.core.database import supabase
from app.core.config import settings
from openai import OpenAI
import json
from fastapi import UploadFile
import io
from pypdf import PdfReader
from typing import Tuple, Dict, Any

class ETLService:
    """
    Service to ingest documents into the Vector Knowledge Base.
    Handles text extraction, AI metadata extraction (Gemini), and vector storage.
    """
    def __init__(self):
        self.openai_client = None
        self._initialize_client()

    def _initialize_client(self):
        if settings.OPENAI_API_KEY:
            # Ensure base_url is properly formatted (strip trailing slash if present)
            base_url = settings.AI_BASE_URL if settings.AI_BASE_URL else "https://api.openai.com/v1"
            if base_url.endswith("/"):
                base_url = base_url[:-1]
                
            self.openai_client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=base_url
            )
            print(f"ETLService: Initialized AI client with base_url: {base_url}")
            
    async def process_file(self, file: UploadFile) -> dict:
        """
        Main entry point for document processing.
        """
        filename = file.filename
        content = await file.read()
        text = ""

        try:
            # 1. Physical Extraction
            if filename.lower().endswith(".pdf"):
                pdf = PdfReader(io.BytesIO(content))
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                print(f"ETL: Extracted {len(text)} chars from PDF: {filename}")
            elif filename.lower().endswith((".txt", ".md", ".csv", ".json")):
                text = content.decode("utf-8")
            else:
                return {"filename": filename, "status": "skipped", "reason": "不支持的文件类型"}

            if not text.strip():
                # Fallback info for UI
                return {"filename": filename, "status": "error", "reason": "无法从文档中提取文字（可能是扫描件或加密文档）"}

            # 2. Logic Pipeline
            success, details = await self.process_text_with_extraction(text, filename, len(content))
            
            return {
                "filename": filename, 
                "status": "success" if success else "failed",
                "extracted_metadata": details,
                "chunks": len(text) // 400
            }
        except Exception as e:
            print(f"ETL CRITICAL ERROR for {filename}: {str(e)}")
            return {"filename": filename, "status": "error", "reason": f"系统解析异常: {str(e)}"}

    async def process_text_with_extraction(self, text: str, filename: str, size: int) -> Tuple[bool, Dict[str, Any]]:
        """
        AI Analysis and DB Storage.
        """
        if not self.openai_client:
            return False, {"error": "未配置 AI 接口"}
            
        if not supabase:
            return False, {"error": "数据库连接失败"}

        # 1. AI Metadata Extraction (Gemini-3-Pro-Preview)
        # Using a safer way to parse JSON since some proxies/models include markdown
        preview_text = text[:4000]
        extracted_data = {
            "doc_type": "other",
            "client_name": "未知客户",
            "amount": 0,
            "date": None,
            "summary": "AI 解析中..."
        }
        
        try:
            prompt = f"""
            你是一个企业文档分析专家。请阅读以下文档内容，提取元数据并以 JSON 格式返回。
            
            JSON 结构要求：
            - doc_type: (字符串：contract, bid, product, proposal, invoice, other)
            - client_name: (字符串：关联的公司或客户名称)
            - amount: (数字：合同或文档涉及的总金额，若无则为 0)
            - date: (字符串：文档日期，格式 YYYY-MM-DD，若无则为 null)
            - summary: (字符串：一句话中文摘要)
            
            文档内容：
            {preview_text}
            """
            
            # Use specific model gemini-3-pro-preview
            response = self.openai_client.chat.completions.create(
                model="gemini-3-pro-preview", 
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
                # Note: Not using json_object response_format here to increase compatibility with aggressive proxies
            )
            
            raw_content = response.choices[0].message.content
            # Cleanup Markdown if present
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_content:
                raw_content = raw_content.split("```")[1].split("```")[0].strip()
                
            extracted_data = json.loads(raw_content)
            print(f"ETL: AI Extracted metadata for {filename}: {extracted_data.get('doc_type')}")
        except Exception as e:
            print(f"ETL: Metadata extraction warn for {filename}: {str(e)}")
            # We don't fail the whole pipeline just because AI metadata failed
            extracted_data["summary"] = f"自动解析摘要失败: {str(e)[:50]}"

        # 2. Database Persistence
        doc_record = {
            "name": filename,
            "doc_type": extracted_data.get("doc_type", "other"),
            "extracted_data": extracted_data,
            "version": 1
        }
        
        try:
            # We use documents table
            res = supabase.table("documents").insert(doc_record).execute()
            if not res.data:
                raise Exception("数据库插入请求未返回数据")
            document_id = res.data[0]['id']
        except Exception as e:
            print(f"ETL: DB Insert failed: {str(e)}")
            return False, {"error": f"数据库写入失败: {str(e)}"}

        # 3. Vectorization (Optional background task if needed, but doing sync now)
        try:
            # Chunking and Embedding
            word_chunks = list(self._chunk_text(text))
            for chunk in word_chunks:
                # We use text-embedding-3-small as standard for pgvector 1536 dims
                emb_res = self.openai_client.embeddings.create(input=chunk, model="text-embedding-3-small")
                embedding = emb_res.data[0].embedding
                
                supabase.table("document_embeddings").insert({
                    "document_id": document_id,
                    "content": chunk,
                    "metadata": {"source": filename},
                    "embedding": embedding
                }).execute()
        except Exception as e:
            # Vector indexing failure isn't fatal to the metadata record
            print(f"ETL: Vector indexing failed for {filename}: {str(e)}")
                
        return True, extracted_data

    def _chunk_text(self, text, chunk_size=500):
        words = text.split()
        for i in range(0, len(words), chunk_size):
            yield " ".join(words[i:i + chunk_size])

etl_service = ETLService()
