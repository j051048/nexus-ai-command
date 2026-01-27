import httpx
import json
import io
import os
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
        
        # RAG Configurable Parameters (Optimization 5)
        # Defaults: Size=600, Overlap=100
        self.chunk_size = int(os.getenv("RAG_CHUNK_SIZE", 600))
        self.chunk_overlap = int(os.getenv("RAG_CHUNK_OVERLAP", 100))
        
    async def _call_ai_raw(self, payload: dict, endpoint: str = "/chat/completions") -> str:
        """
        Low-level HTTP call to the AI proxy. Bypass SDK limitations.
        """
        if not self.api_key:
            raise Exception("AI API Key is missing in environment variables")
            
        # ... logic ...
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
            
    def _scrub_pii(self, content: str) -> str:
        """
        Unified PII scrubbing logic. 
        Enhances privacy protection for sensitive data before DB storage.
        """
        import re
        # 1. Phone Numbers (Simple 11 digits)
        content = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[PHONE_REDACTED]', content)
        
        # 2. Chinese ID Card (18 digits or 17+X)
        # Matches 18-digit ID cards: 6 (Area) + 8 (DOB) + 4 (Suffix)
        # Mask the DOB part (8 digits) with asterisks
        content = re.sub(r'(?<!\d)(\d{6})\d{8}(\d{3}[\dXx])(?!\d)', r'\1********\2', content)
        
        # 3. Email Addresses
        content = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '[EMAIL_REDACTED]', content)
        
        # 4. API Keys / Secrets (Heuristic)
        content = re.sub(r'(?i)(password|passwd|secret|api_key|access_key|token)\s*[:=]\s*[^\s\n,]+', r'\1=[SENSITIVE_REDACTED]', content)
        
        # 5. Private Keys
        content = re.sub(r'-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----', '[PRIVATE_KEY_REDACTED]', content)
        
        return content

    async def create_initial_record(self, filename: str, user_id: str, status: str = "pending") -> str:
        """Creates a placeholder record in the database."""
        if not supabase:
             raise Exception("Supabase not initialized")
        
        record = {
            "name": filename,
            "status": "pending",
            "progress": 0,
            "stage": "uploading",
            "owner_id": user_id,
        }
        res = await supabase.table("documents").insert(record).execute()
        if not res.data:
            raise Exception("Failed to create initial document record")
        return res.data[0]["id"]

    async def _update_progress(self, doc_id: str, progress: int, stage: str, status: str = "processing"):
        """Updates the progress of the document processing."""
        if not doc_id:
            return
        try:
            await supabase.table("documents").update({
                "progress": progress,
                "stage": stage,
                "status": status
            }).eq("id", doc_id).execute()
        except Exception as e:
            print(f"Failed to update progress for {doc_id}: {e}")

    async def process_file(self, content: bytes, filename: str, doc_id: str = None, api_key: str = None, base_url: str = None, user_id: str = None) -> dict:
        text = ""
        
        # Initial Progress Update
        await self._update_progress(doc_id, 10, "parsing")

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

            # Update Progress: Extraction Done
            await self._update_progress(doc_id, 30, "analyzing")

            # 2. Sequential Processing
            success, details = await self.extract_metadata_via_ai(text, filename, active_key, active_url)
            
            # Update Progress: Metadata Done
            await self._update_progress(doc_id, 70, "embedding")

            if success:
                try:
                    # Save Logic: If doc_id exists, update it. If not, create new (legacy path)
                    if doc_id:
                        # Scrub PII
                        safe_text = self._scrub_pii(text)
                        
                        details["full_text_context"] = safe_text[:100000]
                        
                        await supabase.table("documents").update({
                            "extracted_data": details,
                            "doc_type": details.get("doc_type", "other"),
                            "status": "processing" # Still processing embeddings
                        }).eq("id", doc_id).execute()
                    else:
                        # Legacy creation if no doc_id passed
                        doc_id = await self._save_to_db(filename, details, text, user_id=user_id, status="processing")
                    
                    # Generate embeddings
                    embedding_success = await self._generate_embeddings(text, doc_id, filename, active_key, active_url)
                    
                    if embedding_success:
                        # Finalize status
                        await self._update_progress(doc_id, 100, "completed", status="ready")
                        return {
                            "filename": filename, "status": "success", "document_id": doc_id, "metadata": details
                        }
                    else:
                        # P1: Rollback/Mark failed if embeddings fail
                        await supabase.table("documents").update({"status": "failed", "error_log": "Embedding generation partially failed"}).eq("id", doc_id).execute()
                        return {"filename": filename, "status": "partial_success", "reason": "文档已记录，但向量索引失败，搜索可能受限。"}
                        
                except Exception as db_err:
                    print(f"DB Error: {db_err}")
                    if doc_id:
                        await supabase.table("documents").update({"status": "error", "error_log": str(db_err)}).eq("id", doc_id).execute()
                    return {"filename": filename, "status": "error", "reason": f"数据库写入失败: {str(db_err)}"}
            else:
                return {"filename": filename, "status": "error", "reason": f"AI 解析失败: {details.get('error')}"}

        except Exception as e:
            print(f"ETL Panic: {str(e)}")
            if doc_id:
                 await self._update_progress(doc_id, 0, "failed", status="error")
            return {"filename": filename, "status": "error", "reason": f"系统崩溃: {str(e)}"}

    async def extract_metadata_via_ai(self, text: str, filename: str, api_key: str, base_url: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Uses AI to extract structured metadata (JSON) from raw text.
        Supports Tender Analysis (Redlines, Deviations) for 'bid' type documents.
        """
        prompt = f"""
        # Role (角色设定)
        你是一位拥有 20 年经验的资深招投标专家 (Senior Bid Manager) 和项目经理。你擅长快速阅读复杂的招标文件，精准捕捉关键信息，分析潜在风险，并制定高胜率的投标策略。

        # Task (任务)
        请分析以下招标文件内容（全文上下文），按 **6 个核心模块** 进行结构化提取和分析。

        文件名: {filename}
        文件内容片段:
        {text}

        # Output Format (输出格式)
        请输出两个独立的部分，严禁将 Markdown 报告包含在 JSON 字段中。

        第一部分：元数据 (JSON)
        [METADATA_JSON]
        {{
            "doc_type": "bid" | "contract" | "other",
            "client_name": "采购方名称",
            "amount": 预算金额(数字)或null,
            "date": "YYYY-MM-DD",
            "tags": ["核心标签"],
            "redlines": ["提取模块2中的核心否决项(简练列表)"],
            "technical_deviations": ["提取模块3/6中的技术风险点(简练列表)"]
        }}
        [/METADATA_JSON]

        第二部分：完整分析报告 (Markdown)
        [ANALYSIS_REPORT]
        ## 模块 1：项目概况与时间表
        ...
        ## 模块 6：风险预警与专家建议
        ...
        [/ANALYSIS_REPORT]
        """
        
        payload = {
             "messages": [
                {"role": "system", "content": "You are a senior Tender Analyst. Output structured data."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }

        async def call_ai_model(model_name: str, retries=1) -> Tuple[bool, Any]:
            """Helper to call AI with retry logic"""
            payload["model"] = model_name
            try:
                print(f"Attempting AI Analysis with model: {model_name}...")
                async with httpx.AsyncClient(timeout=90.0) as client:
                    response = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
                    
                    if response.status_code != 200:
                        print(f"Model {model_name} failed: {response.status_code} - {response.text}")
                        return False, None
                    
                    return True, response.json()
            except Exception as e:
                print(f"Model {model_name} processing error: {str(e)}")
                return False, None

        # 1. Try Primary Model (Bleeding Edge)
        success, response_json = await call_ai_model("gemini-3-pro-preview")
        
        # 2. Fallback to Stable Model if primary fails
        if not success:
            print("⚠️ Primary model failed. Falling back to Gemini-1.5-Pro...")
            success, response_json = await call_ai_model("gemini-1.5-pro")

        if not success or not response_json:
            return False, {"error": "All AI models failed to process the document."}

        try:
            content = response_json["choices"][0]["message"]["content"]
            
            # Extract JSON
            import re
            json_match = re.search(r'\[METADATA_JSON\](.*?)\[/METADATA_JSON\]', content, re.DOTALL)
            report_match = re.search(r'\[ANALYSIS_REPORT\](.*?)\[/ANALYSIS_REPORT\]', content, re.DOTALL)
            
            metadata = {}
            if json_match:
                try:
                    metadata = json.loads(json_match.group(1).strip())
                except:
                    print("JSON Parse Failed")
            
            if report_match:
                metadata["full_analysis_markdown"] = report_match.group(1).strip()
            elif not json_match:
                # Fallback: if no blocks found, try raw JSON parse (if model ignored instructions)
                try:
                    clean_json = content.replace("```json", "").replace("```", "").strip()
                    metadata = json.loads(clean_json)
                except:
                        pass

            if not metadata:
                    raise Exception("Failed to parse AI output format")

            return True, metadata
        except Exception as e:

            print(f"Metadata Extraction Failed: {e}")
            # Fallback metadata
            return True, {
                "doc_type": "other", 
                "summary": "AI 解析失败，请手动审阅。",
                "client_name": None,
                "amount": 0,
                "date": None,
                "tags": ["解析失败"],
                "redlines": [],
                "technical_deviations": []
            }

    async def _save_to_db(self, filename: str, metadata: dict, text: str = "", user_id: str = None, status: str = "ready") -> str:
        if not supabase:
            raise Exception("Supabase not initialized")
            
        safe_text = self._scrub_pii(text)
        metadata["full_text_context"] = safe_text[:100000] 

        record = {
            "name": filename,
            "doc_type": metadata.get("doc_type", "other"),
            "extracted_data": metadata,
            "version": 1,
            "owner_id": user_id,
            "status": status
        }
        res = await supabase.table("documents").insert(record).execute()
        if not res.data:
            raise Exception("Empty response from database")
        return res.data[0]["id"]

    async def _generate_embeddings(self, text: str, doc_id: str, filename: str, api_key: str, base_url: str) -> bool:
        """
        Batch Embeddings with partial success tracking.
        """
        BATCH_SIZE = 50
        current_batch_text = []
        all_success = True
        
        async def _process_batch(batch_texts):
            try:
                payload = {"model": "text-embedding-3-small", "input": batch_texts}
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
                        return True
                    return False
            except:
                return False

        # Use new dynamic size and overlap
        for chunk in self._semantic_chunk(text, size=self.chunk_size, overlap=self.chunk_overlap):
            current_batch_text.append(chunk)
            if len(current_batch_text) >= BATCH_SIZE:
                if not await _process_batch(current_batch_text):
                    all_success = False
                current_batch_text = []
        
        if current_batch_text:
            if not await _process_batch(current_batch_text):
                all_success = False
        
        return all_success

    def _semantic_chunk(self, text: str, size: int = 600, overlap: int = 100):
        """
        P2 Fix: Improved chunking strategy. 
        Tries to split by double newlines (paragraphs) first, then falls back 
        to sliding window if paragraphs are too large.
        """
        # 1. Clean up excessive whitespace
        import re
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 2. Initial split by double newlines
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        
        for p in paragraphs:
            # If paragraph itself is too large, split it by sentences or characters
            if len(p) > size:
                # If we have something in current_chunk, yield it
                if current_chunk:
                    yield current_chunk
                    current_chunk = ""
                
                # Split large paragraph by sliding window
                start = 0
                while start < len(p):
                    end = start + size
                    chunk = p[start:end]
                    yield chunk
                    start += size - overlap
            else:
                # If current_chunk + new paragraph is within limit
                if len(current_chunk) + len(p) < size:
                    current_chunk += ("\n\n" if current_chunk else "") + p
                else:
                    # Yield current and start new
                    if current_chunk: yield current_chunk
                    current_chunk = p
        
        if current_chunk:
            yield current_chunk

etl_service = ETLService()
