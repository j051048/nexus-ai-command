import httpx
import json
import io
from pypdf import PdfReader
from fastapi import UploadFile
from typing import Tuple, Dict, Any, List
from app.core.database import supabase
from app.core.config import settings

class ETLService:
    """
    Enhanced ETL Service using raw HTTP calls (httpx) to maintain 
    maximum compatibility with 3rd-party proxies like apiyi.com.
    """
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        # Normalize Base URL: Ensure it ends with /v1
        base_url = settings.AI_BASE_URL if settings.AI_BASE_URL else "https://api.openai.com/v1"
        self.base_url = base_url.rstrip("/")
        
    async def _call_ai_raw(self, payload: dict, endpoint: str = "/chat/completions") -> str:
        """
        Low-level HTTP call to the AI proxy. Bypass SDK limitations.
        """
        if not self.api_key:
            raise Exception("AI API Key is missing in environment variables")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                error_msg = response.text
                print(f"AI Provider Error ({response.status_code}): {error_msg}")
                raise Exception(f"AI provider returned error {response.status_code}")
            
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def process_file(self, file: UploadFile, api_key: str = None, base_url: str = None, user_id: str = None) -> dict:
        filename = file.filename
        content = await file.read()
        text = ""
        
        # Use provided config or fall back to system settings
        # URL Normalization: Extract base even if user provided full endpoint
        raw_url = (base_url or self.base_url).split("/chat/completions")[0].split("/embeddings")[0].rstrip("/")
        if "/v1" not in raw_url and "api.openai.com" not in raw_url:
             active_url = f"{raw_url}/v1" if not raw_url.endswith("/v1") else raw_url
        else:
             active_url = raw_url
        active_key = api_key or self.api_key

        try:
            import asyncio
            # 1. Physical Extraction
            if filename.lower().endswith(".pdf"):
                # Offload CPU-bound task to thread to avoid blocking the event loop (TC-06)
                def _parse_pdf():
                    pdf_text = ""
                    reader = PdfReader(io.BytesIO(content))
                    for page in reader.pages:
                        extracted = page.extract_text()
                        if extracted:
                            pdf_text += extracted + "\n"
                    return pdf_text
                text = await asyncio.to_thread(_parse_pdf)
            elif filename.lower().endswith((".txt", ".md", ".csv", ".json")):
                text = content.decode("utf-8")
            elif filename.lower().endswith((".png", ".jpg", ".jpeg")):
                # OCR is already calling an external AI API (async), so it's fine.
                import base64
                base64_image = base64.b64encode(content).decode('utf-8')
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Transcribe the text in this image accurately. Preserve layout if possible."},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                            ]
                        }
                    ],
                    "max_tokens": 4000
                }
                try:
                    text = await self._call_ai_raw(payload, endpoint="/chat/completions")
                except Exception as e:
                    return {"filename": filename, "status": "skipped", "reason": f"OCR Failed: {str(e)}"}
            elif filename.lower().endswith((".docx")):
                def _parse_docx():
                    import docx
                    doc_obj = docx.Document(io.BytesIO(content))
                    return "\n".join([para.text for para in doc_obj.paragraphs])
                try:
                    text = await asyncio.to_thread(_parse_docx)
                except Exception as e:
                    error_str = str(e)
                    if "Bad magic number" in error_str or "File is not a zip file" in error_str:
                         return {"filename": filename, "status": "error", "reason": "文件格式错误。请确认这是标准的 .docx 文件（OpenXML）。"}
                    return {"filename": filename, "status": "error", "reason": f"DOCX 解析失败: {error_str}"}
            else:
                return {"filename": filename, "status": "skipped", "reason": "Unsupported format"}

            if not text.strip():
                return {"filename": filename, "status": "error", "reason": "No text content found"}

            # 2. Sequential Processing
            success, details = await self.extract_metadata_via_ai(text, filename, active_key, active_url)
            
            if success:
                try:
                    doc_id = await self._save_to_db(filename, details, text, user_id=user_id)
                    await self._generate_embeddings(text, doc_id, filename, active_key, active_url)
                    
                    return {
                        "filename": filename, "status": "success", "document_id": doc_id, "metadata": details
                    }
                except Exception as db_err:
                    print(f"DB Error: {db_err}")
                    return {"filename": filename, "status": "error", "reason": f"数据库写入失败: {str(db_err)}"}
            else:
                return {"filename": filename, "status": "error", "reason": f"AI 解析失败: {details.get('error')}"}

        except Exception as e:
            print(f"ETL Panic: {str(e)}")
            return {"filename": filename, "status": "error", "reason": f"系统崩溃: {str(e)}"}

    # ... (extract_metadata_via_ai logic stays)

    async def _save_to_db(self, filename: str, metadata: dict, text: str = "", user_id: str = None) -> str:
        if not supabase:
            raise Exception("Supabase not initialized")
            
        def _scrub_pii(content: str) -> str:
            import re
            # 1. Phone numbers (China)
            content = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[PHONE_REDACTED]', content)
            # 2. ID Cards (China)
            content = re.sub(r'(?<!\d)\d{17}[\d|X](?!\d)', '[ID_REDACTED]', content)
            # 3. Emails (Detection and Redaction)
            content = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '[EMAIL_REDACTED]', content)
            # 4. Sensitive keys/passwords (Common patterns like password=..., api_key=...)
            content = re.sub(r'(?i)(password|passwd|secret|api_key|access_key|token)\s*[:=]\s*[^\s\n,]+', r'\1=[SENSITIVE_REDACTED]', content)
            # 5. Private Keys (RSA/OpenSSH)
            content = re.sub(r'-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----', '[PRIVATE_KEY_REDACTED]', content)
            return content

        safe_text = _scrub_pii(text)
        metadata["full_text_context"] = safe_text[:100000] 

        record = {
            "name": filename,
            "doc_type": metadata.get("doc_type", "other"),
            "extracted_data": metadata,
            "version": 1,
            "owner_id": user_id # Preserve ownership
        }
        res = await supabase.table("documents").insert(record).execute()
        if not res.data:
            raise Exception("Empty response from database")
        return res.data[0]["id"]

    async def _generate_embeddings(self, text: str, doc_id: str, filename: str, api_key: str, base_url: str):
        """
        Medium Fix: Use Batch Embeddings (OpenAI supports array of strings)
        This reduces the number of API calls significantly.
        """
        import asyncio
        
        # Batch size for OpenAI embeddings (max usually 2048, but 50-100 is safer for timeout)
        BATCH_SIZE = 50
        current_batch_text = []
        
        async def _process_batch(batch_texts):
            if not batch_texts: return
            try:
                payload = {
                    "model": "text-embedding-3-small",
                    "input": batch_texts # Array of strings
                }
                headers = {"Authorization": f"Bearer {api_key}"}
                async with httpx.AsyncClient(timeout=45.0) as client:
                    resp = await client.post(f"{base_url}/embeddings", headers=headers, json=payload)
                    if resp.status_code == 200:
                        embeddings_data = resp.json()["data"]
                        records = []
                        for i, item in enumerate(embeddings_data):
                            records.append({
                                "document_id": doc_id,
                                "content": batch_texts[i],
                                "embedding": item["embedding"],
                                "metadata": {"source": filename}
                            })
                        await supabase.table("document_embeddings").insert(records).execute()
                    else:
                        print(f"Batch Embedding API error: {resp.status_code} - {resp.text}")
            except Exception as e:
                print(f"Batch Embedding failed: {e}")

        # Iterate through chunks and fill batches
        for chunk in self._simple_chunk(text):
            current_batch_text.append(chunk)
            if len(current_batch_text) >= BATCH_SIZE:
                await _process_batch(current_batch_text)
                current_batch_text = []
        
        # Final flush
        if current_batch_text:
            await _process_batch(current_batch_text)

    def _simple_chunk(self, text: str, size: int = 500, overlap: int = 50):
        """
        P0 Fix: Character-based chunking with overlap for Chinese text support.
        Previous 'text.split()' failed for CJK languages.
        """
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + size
            yield text[start:end]
            
            # If this chunk reached the end of the text, stop.
            if end >= text_len:
                break
                
            # Move forward by size - overlap to create sliding window
            start += size - overlap

etl_service = ETLService()
