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

    async def process_file(self, file: UploadFile, api_key: str = None, base_url: str = None) -> dict:
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
            # 1. Physical Extraction
            if filename.lower().endswith(".pdf"):
                pdf = PdfReader(io.BytesIO(content))
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
            elif filename.lower().endswith((".txt", ".md", ".csv", ".json")):
                text = content.decode("utf-8")
            elif filename.lower().endswith((".png", ".jpg", ".jpeg")):
                # P3 Optimization: Vision API Support
                import base64
                base64_image = base64.b64encode(content).decode('utf-8')
                
                payload = {
                    "model": "gpt-4o-mini", # Use cost-effective vision model
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
                # P0 Fix: Add DOCX support
                try:
                    import docx
                    doc = docx.Document(io.BytesIO(content))
                    text = "\n".join([para.text for para in doc.paragraphs])
                except Exception as e:
                    error_str = str(e)
                    if "Bad magic number" in error_str or "File is not a zip file" in error_str:
                         return {"filename": filename, "status": "error", "reason": "文件格式错误。请确认这是标准的 .docx 文件（OpenXML）。如果是旧版 .doc 文件，请先用 Word 另存为 .docx。"}
                    return {"filename": filename, "status": "error", "reason": f"DOCX 解析失败: {error_str}"}
            else:
                return {"filename": filename, "status": "skipped", "reason": "Unsupported format"}

            if not text.strip():
                # Provide better hint for scanned PDFs
                if filename.lower().endswith(".pdf"):
                    return {"filename": filename, "status": "error", "reason": "无法提取文本，可能是扫描件 PDF。请尝试截图并作为图片上传。"}
                return {"filename": filename, "status": "error", "reason": "No text content found"}

            # 2. Sequential Processing
            # Step A: Metadata Extraction
            success, details = await self.extract_metadata_via_ai(text, filename, active_key, active_url)
            
            if success:
                # Step B: Database Storage
                try:
                    doc_id = self._save_to_db(filename, details, text)
                    
                    # Step C: Vectorization
                    await self._generate_embeddings(text, doc_id, filename, active_key, active_url)
                    
                    return {
                        "filename": filename,
                        "status": "success",
                        "document_id": doc_id,
                        "metadata": details
                    }
                except Exception as db_err:
                    print(f"DB Error: {db_err}")
                    return {"filename": filename, "status": "error", "reason": f"数据库写入失败: {str(db_err)}"}
            else:
                return {"filename": filename, "status": "error", "reason": f"AI 解析失败: {details.get('error')}"}

        except Exception as e:
            print(f"ETL Panic: {str(e)}")
            return {"filename": filename, "status": "error", "reason": f"系统崩溃: {str(e)}"}

    async def extract_metadata_via_ai(self, text: str, filename: str, api_key: str, base_url: str) -> Tuple[bool, Dict]:
        # P1 Fix: Smart Sampling for Long Documents
        # Combine start, middle and end segments to find metadata (dates, parties, amount)
        total_len = len(text)
        if total_len > 12000:
            start_seg = text[:4000]
            mid_seg = text[total_len//2-2000 : total_len//2+2000]
            end_seg = text[-4000:]
            preview = f"[START]\n{start_seg}\n\n[MIDDLE]\n{mid_seg}\n\n[END]\n{end_seg}"
        else:
            preview = text
            
        # P2: Use centralized prompt
        from app.core.prompts_registry import TOOL_PROMPTS
        prompt = TOOL_PROMPTS["etl_metadata"].format(preview=preview)
        
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }

        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            url = f"{base_url}/chat/completions"

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code != 200:
                    raise Exception(f"AI provider error: {response.status_code}")
                raw_response = response.json()["choices"][0]["message"]["content"]
            # Robust JSON cleaner
            clean_json = raw_response
            if "```json" in raw_response:
                clean_json = raw_response.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_response:
                clean_json = raw_response.split("```")[1].split("```")[0].strip()
            
            data = json.loads(clean_json)
            return True, data
        except Exception as e:
            return False, {"error": str(e)}

    def _save_to_db(self, filename: str, metadata: dict, text: str = "") -> str:
        if not supabase:
            raise Exception("Supabase not initialized")
            
        # P3 Security: PII Scrubbing (Enhanced for P2 Fix)
        def _scrub_pii(content: str) -> str:
            import re
            # Mask Mobile Phones (China) - Use \b boundary to avoid matching inside order numbers
            # Note: \b works for simple word boundaries. For precise Chinese context, lookbehind might be needed, 
            # but for this MVP, \b + standard pattern is safer than before.
            content = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[PHONE_REDACTED]', content)
            # Mask ID Card (Simple regex)
            content = re.sub(r'(?<!\d)\d{17}[\d|X](?!\d)', '[ID_REDACTED]', content)
            return content

        safe_text = _scrub_pii(text)
        metadata["full_text_context"] = safe_text[:100000] 

        record = {
            "name": filename,
            "doc_type": metadata.get("doc_type", "other"),
            "extracted_data": metadata,
            "version": 1
        }
        res = supabase.table("documents").insert(record).execute()
        if not res.data:
            raise Exception("Empty response from database")
        return res.data[0]["id"]

    async def _generate_embeddings(self, text: str, doc_id: str, filename: str, api_key: str, base_url: str):
        """
        P1 Optimization: Generate embeddings in parallel batches (P1: Fix Memory Overflow)
        """
        import asyncio
        
        # Helper to process a single batch of chunks
        async def _process_batch(batch_chunks):
            tasks = []
            for chunk in batch_chunks:
                tasks.append(_fetch_embedding(chunk))
            return await asyncio.gather(*tasks)

        async def _fetch_embedding(chunk):
            try:
                payload = {
                    "model": "text-embedding-3-small",
                    "input": chunk
                }
                headers = {"Authorization": f"Bearer {api_key}"}
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(f"{base_url}/embeddings", headers=headers, json=payload)
                    if resp.status_code == 200:
                        embedding = resp.json()["data"][0]["embedding"]
                        return {
                            "document_id": doc_id,
                            "content": chunk,
                            "embedding": embedding,
                            "metadata": {"source": filename}
                        }
                    else:
                        print(f"Embedding API error: {resp.status_code}")
                        return None
            except Exception as e:
                print(f"Embedding failed for chunk: {e}")
                return None

        # Process generator in batches
        BATCH_SIZE = 50
        current_batch = []
        
        for chunk in self._simple_chunk(text):
            current_batch.append(chunk)

            if len(current_batch) >= BATCH_SIZE:
                results = await _process_batch(current_batch)
                valid_records = [r for r in results if r]
                if valid_records:
                    try:
                        supabase.table("document_embeddings").insert(valid_records).execute()
                    except Exception as e:
                        print(f"Batch db insert failed: {e}")
                current_batch = []
        
        # Process remaining
        if current_batch:
            results = await _process_batch(current_batch)
            valid_records = [r for r in results if r]
            if valid_records:
                try:
                    supabase.table("document_embeddings").insert(valid_records).execute()
                except Exception as e:
                    print(f"Final batch db insert failed: {e}")

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
