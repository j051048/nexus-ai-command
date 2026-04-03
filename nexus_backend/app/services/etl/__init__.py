"""
ETL Package

Composed from split modules:
- file_parsers: Format-specific file parsing (PDF, DOCX, Excel, PPTX, images)
- embedding_gen: Semantic chunking and batch embedding generation

The ETLService class delegates to these modules while preserving the
original public API for backward compatibility.
"""

import hashlib
import io  # noqa: F401
import json
import logging
import re
from typing import Any

import httpx

from app.core.config import settings
from app.core.database import supabase
from app.services.etl.embedding_gen import generate_embeddings, semantic_chunk
from app.services.etl.file_parsers import parse_file_content

logger = logging.getLogger(__name__)


class ETLService:
    """
    Enhanced ETL Service using raw HTTP calls (httpx) to maintain
    maximum compatibility with 3rd-party proxies like apiyi.com.
    """

    _DEFAULT_EMBEDDING_MODEL = "text-embedding-3-large"

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        base_url = settings.AI_BASE_URL if settings.AI_BASE_URL else "https://api.openai.com/v1"
        self.base_url = base_url.rstrip("/")

        from app.core.config import settings as app_settings

        self.chunk_size = app_settings.RAG_CHUNK_SIZE
        self.chunk_overlap = app_settings.RAG_CHUNK_OVERLAP

    async def _call_ai_raw(self, payload: dict, endpoint: str = "/chat/completions") -> str:
        """Low-level HTTP call to the AI proxy."""
        if not self.api_key:
            raise Exception("AI API Key is missing in environment variables")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                error_msg = response.text
                logger.error(f"AI Provider Error ({response.status_code}): {error_msg}")
                raise Exception(f"AI provider returned error {response.status_code}")

            data = response.json()
            return data["choices"][0]["message"]["content"]

    def _scrub_pii(self, content: str) -> str:
        """Unified PII scrubbing logic."""
        content = content.replace("\x00", "")
        content = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[PHONE_REDACTED]", content)
        content = re.sub(r"(?<!\d)(\d{6})\d{8}(\d{3}[\dXx])(?!\d)", r"\1********\2", content)
        content = re.sub(
            r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
            "[EMAIL_REDACTED]",
            content,
        )
        content = re.sub(
            r"(?i)(password|passwd|secret|api_key|access_key|token)\s*[:=]\s*[^\s\n,]+",
            r"\1=[SENSITIVE_REDACTED]",
            content,
        )
        content = re.sub(
            r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----",
            "[PRIVATE_KEY_REDACTED]",
            content,
        )
        return content

    @staticmethod
    def compute_content_hash(content: bytes) -> str:
        """Compute SHA-256 fingerprint of file content for deduplication."""
        return hashlib.sha256(content).hexdigest()

    async def check_duplicate(
        self, content_hash: str, user_id: str, *, org_id: str | None = None, filename: str | None = None
    ) -> dict | None:
        """Multi-level deduplication check."""
        if not supabase:
            return None

        try:
            res = (
                await supabase.table("documents")
                .select("id, name, status, created_at, owner_id")
                .eq("content_hash", content_hash)
                .eq("owner_id", user_id)
                .limit(1)
                .execute()
            )
            if res.data and len(res.data) > 0:
                return {**res.data[0], "dedup_reason": "exact_hash_same_user"}

            if org_id:
                org_res = (
                    await supabase.table("documents")
                    .select("id, name, status, created_at, owner_id")
                    .eq("content_hash", content_hash)
                    .eq("organization_id", org_id)
                    .limit(1)
                    .execute()
                )
                if org_res.data and len(org_res.data) > 0:
                    return {**org_res.data[0], "dedup_reason": "exact_hash_org"}

            if filename and org_id:
                similar = await self._check_title_similarity(filename, org_id)
                if similar:
                    return similar

        except Exception as e:
            logger.error(f"Dedup check failed (non-fatal): {e}")
        return None

    async def _check_title_similarity(self, filename: str, org_id: str, threshold: float = 0.85) -> dict | None:
        """Check for documents with very similar titles within the same org."""
        from difflib import SequenceMatcher

        base_name = filename.rsplit(".", 1)[0] if "." in filename else filename
        normalized = re.sub(r"[\s_\-()（）\[\]【】]+", "", base_name).lower()

        if len(normalized) < 3:
            return None

        try:
            res = (
                await supabase.table("documents")
                .select("id, name, status, created_at, owner_id")
                .eq("organization_id", org_id)
                .in_("status", ["ready", "processing", "pending"])
                .order("created_at", desc=True)
                .limit(200)
                .execute()
            )
            if not res.data:
                return None

            for doc in res.data:
                doc_name = doc.get("name", "")
                doc_base = doc_name.rsplit(".", 1)[0] if "." in doc_name else doc_name
                doc_normalized = re.sub(r"[\s_\-()（）\[\]【】]+", "", doc_base).lower()

                if not doc_normalized:
                    continue

                if normalized == doc_normalized:
                    return {**doc, "dedup_reason": "title_exact"}

                ratio = SequenceMatcher(None, normalized, doc_normalized).ratio()
                if ratio >= threshold:
                    return {**doc, "dedup_reason": f"title_similar({ratio:.0%})"}

        except Exception as e:
            logger.error(f"Title similarity check failed (non-fatal): {e}")
        return None

    async def create_initial_record(
        self,
        filename: str,
        user_id: str,
        status: str = "pending",
        visibility: str = "organization",
        department: str = None,
        content_hash: str = None,
        category: str = "other",
        organization_id: str = None,
    ) -> str:
        """Creates a placeholder record in the database."""
        if not supabase:
            raise Exception("Supabase not initialized")

        if visibility not in ("private", "department", "organization"):
            visibility = "organization"

        if visibility == "department" and not department:
            try:
                user_res = await supabase.table("users").select("department").eq("id", user_id).maybe_single().execute()
                if user_res.data:
                    department = user_res.data.get("department")
            except Exception as e:
                logger.error(f"Failed to fetch user department: {e}")

        record = {
            "name": filename,
            "status": "pending",
            "progress": 0,
            "stage": "uploading",
            "owner_id": user_id,
            "visibility": visibility,
            "department": department,
            "content_hash": content_hash,
            "organization_id": organization_id,
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
            await (
                supabase.table("documents")
                .update({"progress": progress, "stage": stage, "status": status})
                .eq("id", doc_id)
                .execute()
            )
        except Exception as e:
            logger.error(f"Failed to update progress for {doc_id}: {e}")

    async def _mark_doc_error(self, doc_id: str, reason: str):
        """Mark a document as failed."""
        if not doc_id or not supabase:
            return
        try:
            await (
                supabase.table("documents")
                .update({"status": "error", "stage": "failed", "error_log": reason[:500]})
                .eq("id", doc_id)
                .execute()
            )
        except Exception as e:
            logger.error(f"Failed to mark doc {doc_id} as error: {e}")

    async def process_file(
        self,
        content: bytes,
        filename: str,
        doc_id: str = None,
        api_key: str = None,
        base_url: str = None,
        user_id: str = None,
        organization_id: str = None,
    ) -> dict:
        """Main ETL pipeline: parse -> extract metadata -> generate embeddings."""
        await self._update_progress(doc_id, 10, "parsing")

        raw_url = (base_url or self.base_url).split("/chat/completions")[0].split("/embeddings")[0].rstrip("/")
        if "/v1" not in raw_url and "api.openai.com" not in raw_url:
            active_url = f"{raw_url}/v1" if not raw_url.endswith("/v1") else raw_url
        else:
            active_url = raw_url
        active_key = api_key or self.api_key

        try:
            # 1. Parse file (delegated to file_parsers module)
            text, parse_error = await parse_file_content(content, filename, self._call_ai_raw)

            if parse_error:
                await self._mark_doc_error(doc_id, parse_error.get("reason", "Parse failed"))
                return parse_error

            if not text.strip():
                await self._mark_doc_error(doc_id, "No text content found")
                return {"filename": filename, "status": "error", "reason": "No text content found"}

            text = text.replace("\x00", "")
            await self._update_progress(doc_id, 30, "analyzing")

            # 2. AI metadata extraction
            success, details = await self.extract_metadata_via_ai(text, filename, active_key, active_url)
            await self._update_progress(doc_id, 70, "embedding")

            if success:
                try:
                    if doc_id:
                        safe_text = self._scrub_pii(text)
                        details["full_text_context"] = safe_text[:100000]

                        await (
                            supabase.table("documents")
                            .update({
                                "extracted_data": details,
                                "doc_type": details.get("doc_type", "other"),
                                "status": "processing",
                            })
                            .eq("id", doc_id)
                            .execute()
                        )
                    else:
                        doc_id = await self._save_to_db(
                            filename, details, text,
                            user_id=user_id, status="processing",
                            organization_id=organization_id,
                        )

                    safe_text_for_embedding = self._scrub_pii(text)

                    # 3. Generate embeddings (delegated to embedding_gen module)
                    embedding_success = await generate_embeddings(
                        safe_text_for_embedding,
                        doc_id,
                        filename,
                        active_key,
                        active_url,
                        organization_id=organization_id,
                        default_embedding_model=self._DEFAULT_EMBEDDING_MODEL,
                        chunk_size=self.chunk_size,
                        chunk_overlap=self.chunk_overlap,
                    )

                    if embedding_success:
                        await self._update_progress(doc_id, 100, "completed", status="ready")
                        return {
                            "filename": filename,
                            "status": "success",
                            "document_id": doc_id,
                            "metadata": details,
                        }
                    else:
                        await (
                            supabase.table("documents")
                            .update({
                                "status": "failed",
                                "error_log": "Embedding generation partially failed",
                            })
                            .eq("id", doc_id)
                            .execute()
                        )
                        return {
                            "filename": filename,
                            "status": "partial_success",
                            "reason": "文档已记录，但向量索引失败，搜索可能受限。",
                        }

                except Exception as db_err:
                    logger.error(f"DB Error: {db_err}")
                    if doc_id:
                        await (
                            supabase.table("documents")
                            .update({"status": "error", "error_log": str(db_err)})
                            .eq("id", doc_id)
                            .execute()
                        )
                    return {
                        "filename": filename,
                        "status": "error",
                        "reason": f"数据库写入失败: {str(db_err)}",
                    }
            else:
                await self._mark_doc_error(doc_id, f"AI 解析失败: {details.get('error')}")
                return {
                    "filename": filename,
                    "status": "error",
                    "reason": f"AI 解析失败: {details.get('error')}",
                }

        except Exception as e:
            logger.error(f"ETL Panic: {str(e)}")
            if doc_id:
                await self._update_progress(doc_id, 0, "failed", status="error")
            return {
                "filename": filename,
                "status": "error",
                "reason": f"系统崩溃: {str(e)}",
            }

    async def extract_metadata_via_ai(
        self, text: str, filename: str, api_key: str, base_url: str
    ) -> tuple[bool, dict[str, Any]]:
        """Uses AI to extract structured metadata from raw text."""
        _fn_lower = filename.lower()
        _filename_hint = "other"
        _filename_keywords = {
            "product": ["彩页", "产品资料", "产品手册", "产品说明", "规格书", "datasheet", "brochure", "产品目录", "catalog"],
            "contract": ["合同", "协议", "contract"],
            "tender": ["招标", "招标文件", "tender", "招标公告", "采购需求"],
            "bid": ["投标", "投标书", "标书", "bid", "应标", "响应文件"],
            "proposal": ["方案", "proposal"],
            "invoice": ["发票", "invoice"],
        }
        for _dtype, _keywords in _filename_keywords.items():
            if any(kw in _fn_lower for kw in _keywords):
                _filename_hint = _dtype
                break

        prompt = f"""
        # Role
        你是一位拥有 20 年经验的资深招投标专家和项目经理。

        # Task
        请分析以下文件内容，按 6 个核心模块进行结构化提取和分析。

        文件名: {filename}
        文件名预分类提示: {_filename_hint}
        文件内容片段:
        {text[:80000]}

        # Output Format
        第一部分：元数据 (JSON)
        [METADATA_JSON]
        {{
            "doc_type": "tender" | "bid" | "contract" | "product" | "proposal" | "invoice" | "other",
            "client_name": "采购方/客户名称",
            "amount": 预算金额(数字)或null,
            "date": "YYYY-MM-DD",
            "tags": ["核心标签"],
            "redlines": ["核心否决项"],
            "technical_deviations": ["技术风险点"]
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
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async def call_ai_model(model_name: str, retries=1) -> tuple[bool, Any]:
            payload["model"] = model_name
            try:
                logger.info(f"Attempting AI Analysis with model: {model_name}...")
                async with httpx.AsyncClient(timeout=90.0) as client:
                    response = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
                    if response.status_code != 200:
                        logger.warning(f"Model {model_name} failed: {response.status_code} - {response.text}")
                        return False, None
                    return True, response.json()
            except Exception as e:
                logger.warning(f"Model {model_name} processing error: {str(e)}")
                return False, None

        success, response_json = await call_ai_model("gemini-3-pro-preview")

        if not success:
            logger.warning("Primary model failed. Falling back to Gemini-2.5-Pro...")
            success, response_json = await call_ai_model("gemini-2.5-pro")

        if not success or not response_json:
            return False, {"error": "All AI models failed to process the document."}

        try:
            content_text = response_json["choices"][0]["message"]["content"]

            json_match = re.search(r"\[METADATA_JSON\](.*?)\[/METADATA_JSON\]", content_text, re.DOTALL)
            report_match = re.search(r"\[ANALYSIS_REPORT\](.*?)\[/ANALYSIS_REPORT\]", content_text, re.DOTALL)

            metadata = {}
            if json_match:
                try:
                    metadata = json.loads(json_match.group(1).strip())
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON Parse Failed: {e}")

            if report_match:
                metadata["full_analysis_markdown"] = report_match.group(1).strip()
            elif not json_match:
                try:
                    clean_json = content_text.replace("```json", "").replace("```", "").strip()
                    metadata = json.loads(clean_json)
                except json.JSONDecodeError:
                    pass

            if not metadata:
                raise Exception("Failed to parse AI output format")

            return True, metadata
        except Exception as e:
            logger.warning(f"Metadata Extraction Failed: {e}")
            return True, {
                "doc_type": "other",
                "summary": "AI 解析失败，请手动审阅。",
                "client_name": None,
                "amount": 0,
                "date": None,
                "tags": ["解析失败"],
                "redlines": [],
                "technical_deviations": [],
            }

    async def _save_to_db(
        self,
        filename: str,
        metadata: dict,
        text: str = "",
        user_id: str = None,
        status: str = "ready",
        visibility: str = "organization",
        department: str = None,
        organization_id: str = None,
    ) -> str:
        """Save document to database with visibility control."""
        if not supabase:
            raise Exception("Supabase not initialized")

        if visibility not in ("private", "department", "organization"):
            visibility = "organization"

        safe_text = self._scrub_pii(text)
        metadata["full_text_context"] = safe_text[:100000]

        record = {
            "name": filename,
            "doc_type": metadata.get("doc_type", "other"),
            "extracted_data": metadata,
            "version": 1,
            "owner_id": user_id,
            "status": status,
            "visibility": visibility,
            "department": department,
            "organization_id": organization_id,
        }
        res = await supabase.table("documents").insert(record).execute()
        if not res.data:
            raise Exception("Empty response from database")
        return res.data[0]["id"]

    def _semantic_chunk(self, text: str, size: int = 600, overlap: int = 100):
        """Delegate to module-level semantic_chunk for backward compatibility."""
        return semantic_chunk(text, size, overlap)

    async def _generate_embeddings(
        self,
        text: str,
        doc_id: str,
        filename: str,
        api_key: str,
        base_url: str,
        organization_id: str = None,
    ) -> bool:
        """Delegate to module-level generate_embeddings for backward compatibility."""
        return await generate_embeddings(
            text, doc_id, filename, api_key, base_url,
            organization_id=organization_id,
            default_embedding_model=self._DEFAULT_EMBEDDING_MODEL,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )


etl_service = ETLService()
