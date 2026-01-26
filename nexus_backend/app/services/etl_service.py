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
            self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
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
                    text += page.extract_text() + "\n"
            elif filename.lower().endswith((".txt", ".md", ".csv", ".json")):
                text = content.decode("utf-8")
            else:
                return {"filename": filename, "status": "skipped", "reason": "Unsupported file type"}

            if not text.strip():
                return {"filename": filename, "status": "error", "reason": "No text extracted"}

            success, details = await self.process_text_with_extraction(text, filename, len(content))
            
            return {
                "filename": filename, 
                "status": "success" if success else "failed",
                "extracted_metadata": details,
                "chunks_processed": len(text) // 300
            }
        except Exception as e:
            return {"filename": filename, "status": "error", "reason": str(e)}

    async def process_text_with_extraction(self, text: str, filename: str, size: int) -> Tuple[bool, Dict[str, Any]]:
        """
        Intelligent Ingestion: 
        1. Extract metadata with AI
        2. Store in Relational DB
        3. Embed and store in Vector DB
        """
        if not self.openai_client or not supabase:
            return False, {"error": "AI client or DB not initialized"}

        # 1. AI Metadata Extraction
        preview_text = text[:3000] 
        extracted_data = {}
        try:
            prompt = f"""
            Extract metadata from this document (JSON only):
            - doc_type: (contract, bid, product, proposal, invoice, other)
            - client_name: (string or null)
            - amount: (number or null)
            - date: (YYYY-MM-DD or null)
            - summary: (1 sentence summary)
            
            Content:
            {preview_text}
            """
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            extracted_data = json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Metadata extraction failed: {e}")
            extracted_data = {"doc_type": "other", "summary": "Extraction failed"}

        # 2. Save to 'documents' table
        doc_record = {
            "name": filename,
            "doc_type": extracted_data.get("doc_type", "other"),
            "extracted_data": extracted_data,
            "version": 1
        }
        
        try:
            # We assume the 'documents' table exists
            res = supabase.table("documents").insert(doc_record).execute()
            if not res.data:
                raise Exception("DB Insert produced no data")
            document_id = res.data[0]['id']
        except Exception as e:
            print(f"Database insertion failed for metadata: {e}")
            return False, {"error": f"DB Insert failed: {str(e)}"}

        # 3. Vectorization & Chunk Storage
        chunks = list(self._chunk_text(text))
        for chunk in chunks:
            try:
                emb_res = self.openai_client.embeddings.create(input=chunk, model="text-embedding-3-small")
                embedding = emb_res.data[0].embedding
                
                supabase.table("document_embeddings").insert({
                    "document_id": document_id,
                    "content": chunk,
                    "metadata": {"source": filename},
                    "embedding": embedding
                }).execute()
            except Exception as e:
                print(f"Chunk embedding failed: {e}")
                
        return True, extracted_data

    def _chunk_text(self, text, chunk_size=300):
        tokens = text.split()
        for i in range(0, len(tokens), chunk_size):
            yield " ".join(tokens[i:i + chunk_size])

etl_service = ETLService()
