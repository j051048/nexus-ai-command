"""
P2 Enhancement: Multimodal Input Service

Implements support for images, files, and voice input.
Fixes Issue #20: No image/voice/file upload support.

Phase 4.6: Enhanced with configurable vision model, context-aware prompts,
image URL passthrough, and improved document parsing.
"""

import base64
import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class InputType(Enum):
    """Types of multimodal input."""
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    FILE = "file"
    VIDEO = "video"
    CODE = "code"


class FileCategory(Enum):
    """Categories of files."""
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    CODE = "code"
    ARCHIVE = "archive"
    OTHER = "other"


@dataclass
class MultimodalInput:
    """Multimodal input data."""
    input_type: InputType
    content: Any
    metadata: dict[str, Any] = field(default_factory=dict)
    file_path: str | None = None
    file_name: str | None = None
    file_size: int | None = None
    mime_type: str | None = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ProcessedInput:
    """Processed multimodal input ready for LLM."""
    text_content: str = ""
    image_urls: list[str] = field(default_factory=list)
    image_descriptions: list[str] = field(default_factory=list)
    file_contents: list[dict[str, Any]] = field(default_factory=list)
    voice_transcript: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MultimodalService:
    """
    P2 Enhancement: Multimodal input handling.

    Phase 4.6 enhancements:
    - Configurable vision model (via settings / per-request)
    - Context-aware image analysis prompts for business use
    - Image URL passthrough support
    - Basic PDF text extraction
    - Lazy initialization of OpenAI client via AIService
    """

    # Supported file types
    SUPPORTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    SUPPORTED_AUDIO_TYPES = ["audio/mp3", "audio/mpeg", "audio/wav", "audio/m4a", "audio/webm"]
    SUPPORTED_DOC_TYPES = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]

    # Max file sizes (in bytes)
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_AUDIO_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_FILE_SIZE = 20 * 1024 * 1024   # 20MB

    def __init__(self):
        self._openai_client = None

    def _get_openai_client(self):
        """Lazy-initialize an AsyncOpenAI client from app settings."""
        if self._openai_client is None:
            try:
                from openai import AsyncOpenAI

                from app.core.config import settings

                self._openai_client = AsyncOpenAI(
                    api_key=settings.OPENAI_API_KEY or settings.AI_API_KEY,
                    base_url=settings.AI_BASE_URL or "https://api.openai.com/v1",
                )
            except Exception as e:
                logger.warning(f"Failed to init OpenAI client for multimodal: {e}")
        return self._openai_client

    def _get_vision_model(self, config: dict | None = None) -> str:
        """Get the vision-capable model name from config or settings."""
        if config and config.get("vision_model"):
            return config["vision_model"]
        try:
            from app.core.config import settings
            return getattr(settings, "AI_VISION_MODEL", None) or settings.AI_DEFAULT_MODEL or "gpt-4o-mini"
        except Exception:
            return "gpt-4o-mini"

    async def process_input(
        self,
        input_data: MultimodalInput,
        config: dict | None = None,
    ) -> ProcessedInput:
        """
        Process multimodal input into LLM-ready format.

        Args:
            input_data: MultimodalInput object
            config: Optional config dict with vision_model, context, etc.

        Returns:
            ProcessedInput ready for LLM consumption
        """
        result = ProcessedInput(metadata=input_data.metadata)

        if input_data.input_type == InputType.TEXT:
            result.text_content = input_data.content

        elif input_data.input_type == InputType.IMAGE:
            processed = await self._process_image(input_data, config)
            result.text_content = processed.get("description", "")
            result.image_urls = processed.get("urls", [])
            result.image_descriptions = [processed.get("description", "")]

        elif input_data.input_type == InputType.VOICE:
            processed = await self._process_voice(input_data)
            result.text_content = processed.get("transcript", "")
            result.voice_transcript = processed.get("transcript", "")

        elif input_data.input_type == InputType.FILE:
            processed = await self._process_file(input_data)
            result.text_content = processed.get("content", "")
            result.file_contents = [processed]

        return result

    async def _process_image(
        self, input_data: MultimodalInput, config: dict | None = None
    ) -> dict:
        """Process image input — supports base64, bytes, and URL."""
        result: dict[str, Any] = {"urls": [], "description": ""}

        image_bytes: bytes | None = None
        image_url: str | None = None

        # Detect input format
        if isinstance(input_data.content, str):
            if input_data.content.startswith("data:"):
                # base64 data URI
                header, data = input_data.content.split(",", 1)
                image_bytes = base64.b64decode(data)
            elif input_data.content.startswith(("http://", "https://")):
                # URL passthrough
                image_url = input_data.content
                result["urls"].append(image_url)
            else:
                return result
        elif isinstance(input_data.content, bytes):
            image_bytes = input_data.content
        else:
            return result

        # Generate hash for deduplication if we have bytes
        if image_bytes:
            hashlib.md5(image_bytes).hexdigest()
            # Create data URI for vision API
            image_url = f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode()}"

        # Analyze with vision model
        client = self._get_openai_client()
        if client and image_url:
            try:
                description = await self._analyze_image_with_llm(
                    image_url, config
                )
                result["description"] = description
            except Exception as e:
                logger.warning(f"Image analysis failed: {e}")
                result["description"] = "[图片内容]"

        return result

    async def _analyze_image_with_llm(
        self, image_url: str, config: dict | None = None
    ) -> str:
        """Analyze image content using vision model with context-aware prompts."""
        client = self._get_openai_client()
        if not client:
            return "[图片]"

        model = self._get_vision_model(config)
        conversation_context = (config or {}).get("context", "")

        # Build context-aware prompt for business use
        if conversation_context:
            prompt = (
                f"用户正在讨论: {conversation_context}\n\n"
                "请分析这张图片，重点关注与当前讨论相关的信息。"
                "如果是图表/数据截图，提取关键数据点；"
                "如果是发票/收据，提取金额和关键信息；"
                "如果是文档截图，提取核心内容。用中文简洁回复。"
            )
        else:
            prompt = (
                "请分析这张图片的内容。"
                "如果是图表或数据可视化，提取关键数据点和趋势；"
                "如果是发票/收据/合同截图，提取金额、日期等关键信息；"
                "如果是其他内容，简洁描述。用中文回复。"
            )

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url},
                            },
                        ],
                    }
                ],
                max_tokens=500,
            )

            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return "[图片内容无法解析]"

    async def _process_voice(self, input_data: MultimodalInput) -> dict:
        """Process voice input."""
        result = {"transcript": ""}

        # Handle base64 audio
        if isinstance(input_data.content, str) and input_data.content.startswith("data:"):
            header, data = input_data.content.split(",", 1)
            audio_bytes = base64.b64decode(data)
        elif isinstance(input_data.content, bytes):
            audio_bytes = input_data.content
        else:
            return result

        client = self._get_openai_client()
        if client:
            try:
                transcript = await self._transcribe_audio(audio_bytes)
                result["transcript"] = transcript
            except Exception as e:
                logger.warning(f"Audio transcription failed: {e}")
                result["transcript"] = "[语音内容无法转写]"

        return result

    async def _transcribe_audio(self, audio_bytes: bytes) -> str:
        """Transcribe audio using Whisper."""
        client = self._get_openai_client()
        if not client:
            return "[语音]"

        try:
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_bytes)
                temp_path = f.name

            try:
                with open(temp_path, "rb") as audio_file:
                    transcript = await client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="zh",
                    )
                return transcript.text
            finally:
                os.unlink(temp_path)

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return "[语音转写失败]"

    async def _process_file(self, input_data: MultimodalInput) -> dict:
        """Process file input."""
        result: dict[str, Any] = {"content": "", "metadata": {}}

        mime_type = input_data.mime_type or "application/octet-stream"
        file_name = input_data.file_name or "unknown"

        result["metadata"] = {
            "file_name": file_name,
            "file_size": input_data.file_size,
            "mime_type": mime_type,
            "category": self._categorize_file(mime_type).value,
        }

        # Extract text content based on file type
        if mime_type in self.SUPPORTED_DOC_TYPES:
            content = await self._extract_document_content(
                input_data.content, mime_type
            )
            result["content"] = content
        else:
            result["content"] = f"[文件: {file_name}]"

        return result

    def _categorize_file(self, mime_type: str) -> FileCategory:
        """Categorize file by mime type."""
        if mime_type.startswith("image/"):
            return FileCategory.IMAGE
        elif mime_type.startswith("audio/"):
            return FileCategory.AUDIO
        elif mime_type.startswith("video/"):
            return FileCategory.VIDEO
        elif "pdf" in mime_type or "document" in mime_type or "word" in mime_type:
            return FileCategory.DOCUMENT
        elif "sheet" in mime_type or "excel" in mime_type or "csv" in mime_type:
            return FileCategory.SPREADSHEET
        elif "zip" in mime_type or "rar" in mime_type or "tar" in mime_type:
            return FileCategory.ARCHIVE
        elif "code" in mime_type or "javascript" in mime_type or "python" in mime_type:
            return FileCategory.CODE
        return FileCategory.OTHER

    async def _extract_document_content(
        self, content: Any, mime_type: str
    ) -> str:
        """Extract text content from document."""
        if mime_type in ("text/plain", "text/csv"):
            if isinstance(content, bytes):
                return content.decode("utf-8", errors="ignore")
            return str(content)

        # PDF extraction
        if "pdf" in mime_type:
            return await self._extract_pdf_text(content)

        # For other document types (Word, Excel) — return metadata-only
        return "[文档内容 — 需要在线预览]"

    async def _extract_pdf_text(self, content: Any) -> str:
        """Extract text from PDF using PyPDF2 if available, else fallback."""
        pdf_bytes = content if isinstance(content, bytes) else None
        if not pdf_bytes:
            return "[PDF文档]"

        # Try PyPDF2
        try:
            import io

            from PyPDF2 import PdfReader

            reader = PdfReader(io.BytesIO(pdf_bytes))
            pages_text = []
            for i, page in enumerate(reader.pages[:20]):  # Max 20 pages
                text = page.extract_text()
                if text:
                    pages_text.append(f"[第{i+1}页]\n{text}")

            if pages_text:
                full_text = "\n\n".join(pages_text)
                # Truncate to reasonable length
                if len(full_text) > 5000:
                    return full_text[:5000] + "\n\n[... 文档内容已截断]"
                return full_text
            return "[PDF文档 — 无可提取文字（可能为扫描件）]"
        except ImportError:
            logger.debug("PyPDF2 not installed, PDF text extraction unavailable")
            return "[PDF文档 — 请安装 PyPDF2 以提取文字]"
        except Exception as e:
            logger.warning(f"PDF extraction failed: {e}")
            return "[PDF文档 — 解析失败]"

    def validate_file(self, file_size: int, mime_type: str) -> tuple[bool, str]:
        """
        Validate file size and type.

        Returns:
            (is_valid, error_message)
        """
        if mime_type in self.SUPPORTED_IMAGE_TYPES:
            if file_size > self.MAX_IMAGE_SIZE:
                return False, f"图片大小超过限制 ({self.MAX_IMAGE_SIZE / 1024 / 1024:.0f}MB)"
        elif mime_type in self.SUPPORTED_AUDIO_TYPES:
            if file_size > self.MAX_AUDIO_SIZE:
                return False, f"音频大小超过限制 ({self.MAX_AUDIO_SIZE / 1024 / 1024:.0f}MB)"
        else:
            if file_size > self.MAX_FILE_SIZE:
                return False, f"文件大小超过限制 ({self.MAX_FILE_SIZE / 1024 / 1024:.0f}MB)"

        return True, ""

    def format_for_llm(self, processed: ProcessedInput) -> list[dict]:
        """
        Format processed input for LLM API.

        Returns:
            List of message content parts
        """
        parts = []

        # Add text content
        if processed.text_content:
            parts.append({"type": "text", "text": processed.text_content})

        # Add images
        for url in processed.image_urls:
            parts.append({
                "type": "image_url",
                "image_url": {"url": url},
            })

        # Add file context
        if processed.file_contents:
            file_context = "\n".join([
                f"附件: {f['metadata'].get('file_name', 'unknown')}\n{f['content'][:500]}"
                for f in processed.file_contents
            ])
            parts.append({"type": "text", "text": f"\n[附件内容]\n{file_context}"})

        return parts


# Global instance (lazy-initialized with app settings)
multimodal_service = MultimodalService()
