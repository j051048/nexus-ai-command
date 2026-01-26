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
    Handles text extraction, AI metadata extraction, and vector storage.
    """
    def __init__(self):
        self.openai_client = None
        if settings.OPENAI_API_KEY:
            # Using base_url to support Gemini via OpenAI-Compatible proxies (e.g. flydao)
            self.openai_client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.AI_BASE_URL
            )
            
    async def process_file(self, file: UploadFile) -> dict:
        """
        Extract text from file and execute the ETL pipeline.
        """
        filename = file.filename
        content = await file.read()
        text = ""

        try:
            if filename.lower().endswith(".pdf"):
                pdf = PdfReader(io.BytesIO(content))
                for page in pdf.pages:
                    extracted_text = page.extract_text()
                    if extracted_text:
                        text += extracted_text + "\n"
            elif filename.lower().endswith((".txt", ".md", ".csv", ".json")):
                text = content.decode("utf-8")
            else:
                return {"filename": filename, "status": "skipped", "reason": f"Unsupported file type: {filename}"}

            if not text.strip():
                return {"filename": filename, "status": "error", "reason": "No text extracted from document"}

            success, details = await self.process_text_with_extraction(text, filename, len(content))
            
            return {
                "filename": filename, 
                "status": "success" if success else "failed",
                "extracted_metadata": details,
                "chunks_processed": len(text) // 300
            }
        except Exception as e:
            print(f"ETL Critical Error for {filename}: {str(e)}")
            return {"filename": filename, "status": "error", "reason": f"Pipeline crash: {str(e)}"}

    async def process_text_with_extraction(self, text: str, filename: str, size: int) -> Tuple[bool, Dict[str, Any]]:
        """
        Intelligent Ingestion: 
        1. Extract metadata with AI (using Gemini Flash)
        2. Store in Relational DB
        3. Embed and store in Vector DB
        """
        if not self.openai_client:
            return False, {"error": "AI client not initialized (check API Key)"}
            
        if not supabase:
            return False, {"error": "Database client not initialized (check Supabase settings)"}

        # 1. AI Metadata Extraction
        # Note: Using gemini-1.5-flash which is the standard Flash model name. 
        # gemini-3-flash-preview currently does not exist in standard APIs.
        preview_text = text[:4000] 
        extracted_data = {}
        try:
            prompt = f"""
            Extract specific metadata from this document and return ONLY a JSON object:
            - doc_type: (choose one: contract, bid, product, proposal, invoice, other)
            - client_name: (official name or null)
            - amount: (total currency value as number or null)
            - date: (document date as YYYY-MM-DD or null)
            - summary: (one sentence descriptive summary in Chinese)
            
            Content:
            {preview_text}
            """
            response = self.openai_client.chat.completions.create(
                model="gemini-3-pro-preview", 
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            extracted_data = json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"AI Metadata extraction failed: {str(e)}")
            extracted_data = {"doc_type": "other", "summary": f"AI Parsing error: {str(e)}"}

        # 2. Save to 'documents' table
        doc_record = {
            "name": filename,
            "doc_type": extracted_data.get("doc_type", "other"),
            "extracted_data": extracted_data,
            "version": 1
        }
        
        try:
            insert_res = supabase.table("documents").insert(doc_record).execute()
            # MiniSupabaseClient (SyncPostgrestClient) returns result with .data or might throw
            if not insert_res.data or len(insert_res.data) == 0:
                raise Exception("Database insertion failed to return data")
            document_id = insert_res.data[0]['id']
        except Exception as e:
            print(f"Database insertion failed for document metadata: {str(e)}")
            return False, {"error": f"DB Metadata Insert fail: {str(e)}"}

        # 3. Vectorization & Chunk Storage
        chunks = list(self._chunk_text(text))
        for chunk in chunks:
            try:
                # Still using OpenAI for embeddings as pgvector is configured for 1536 dims usually
                emb_res = self.openai_client.embeddings.create(input=chunk, model="text-embedding-3-small")
                embedding = emb_res.data[0].embedding
                
                supabase.table("document_embeddings").insert({
                    "document_id": document_id,
                    "content": chunk,
                    "metadata": {"source": filename},
                    "embedding": embedding
                }).execute()
            except Exception as e:
                print(f"Chunk embedding/store fail: {str(e)}")
                
        return True, extracted_data

    def _chunk_text(self, text, chunk_size=400):
        words = text.split()
        for i in range(0, len(words), chunk_size):
            yield " ".join(words[i:i + chunk_size])

etl_service = ETLService()
