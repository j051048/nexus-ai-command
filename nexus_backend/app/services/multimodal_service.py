"""
P2 Enhancement: Multimodal Input Service

Implements support for images, files, and voice input.
Fixes Issue #20: No image/voice/file upload support.
"""

import os
import json
import logging
import base64
import hashlib
from typing import Dict, Optional, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio

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
    metadata: Dict[str, Any] = field(default_factory=dict)
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ProcessedInput:
    """Processed multimodal input ready for LLM."""
    text_content: str
    image_urls: List[str] = field(default_factory=list)
    image_descriptions: List[str] = field(default_factory=list)
    file_contents: List[Dict[str, Any]] = field(default_factory=list)
    voice_transcript: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MultimodalService:
    """
    P2 Enhancement: Multimodal input handling.
    
    Features:
    - Image upload and analysis
    - Voice transcription
    - File parsing
    - Content extraction
    - LLM-ready formatting
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
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ]
    
    # Max file sizes (in bytes)
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_AUDIO_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_FILE_SIZE = 20 * 1024 * 1024   # 20MB
    
    def __init__(self, storage_client=None, llm_client=None):
        self.storage = storage_client
        self.llm = llm_client
    
    async def process_input(
        self,
        input_data: MultimodalInput
    ) -> ProcessedInput:
        """
        Process multimodal input into LLM-ready format.
        
        Args:
            input_data: MultimodalInput object
            
        Returns:
            ProcessedInput ready for LLM consumption
        """
        result = ProcessedInput(metadata=input_data.metadata)
        
        if input_data.input_type == InputType.TEXT:
            result.text_content = input_data.content
        
        elif input_data.input_type == InputType.IMAGE:
            processed = await self._process_image(input_data)
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
    
    async def _process_image(self, input_data: MultimodalInput) -> Dict:
        """Process image input."""
        result = {"urls": [], "description": ""}
        
        # Handle base64 image
        if isinstance(input_data.content, str) and input_data.content.startswith("data:"):
            # Extract base64 data
            header, data = input_data.content.split(",", 1)
            image_bytes = base64.b64decode(data)
        elif isinstance(input_data.content, bytes):
            image_bytes = input_data.content
        else:
            return result
        
        # Generate hash for deduplication
        image_hash = hashlib.md5(image_bytes).hexdigest()
        
        # Upload to storage if available
        if self.storage:
            try:
                file_name = f"images/{image_hash}.jpg"
                url = await self.storage.upload(file_name, image_bytes)
                result["urls"].append(url)
            except Exception as e:
                logger.warning(f"Image upload failed: {e}")
        
        # Generate description with LLM (Vision)
        if self.llm:
            try:
                description = await self._analyze_image_with_llm(image_bytes)
                result["description"] = description
            except Exception as e:
                logger.warning(f"Image analysis failed: {e}")
                result["description"] = "[图片内容]"
        
        return result
    
    async def _analyze_image_with_llm(self, image_bytes: bytes) -> str:
        """Analyze image content using vision model."""
        if not self.llm:
            return "[图片]"
        
        try:
            # Convert to base64
            base64_image = base64.b64encode(image_bytes).decode()
            
            # Use vision model
            response = await self.llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "请描述这张图片的内容。"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=300
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return "[图片内容无法解析]"
    
    async def _process_voice(self, input_data: MultimodalInput) -> Dict:
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
        
        # Transcribe audio
        if self.llm:
            try:
                transcript = await self._transcribe_audio(audio_bytes)
                result["transcript"] = transcript
            except Exception as e:
                logger.warning(f"Audio transcription failed: {e}")
                result["transcript"] = "[语音内容无法转写]"
        
        return result
    
    async def _transcribe_audio(self, audio_bytes: bytes) -> str:
        """Transcribe audio using Whisper or similar."""
        if not self.llm:
            return "[语音]"
        
        try:
            # Use OpenAI Whisper
            import tempfile
            
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_bytes)
                temp_path = f.name
            
            try:
                with open(temp_path, "rb") as audio_file:
                    transcript = await self.llm.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="zh"
                    )
                return transcript.text
            finally:
                os.unlink(temp_path)
        
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return "[语音转写失败]"
    
    async def _process_file(self, input_data: MultimodalInput) -> Dict:
        """Process file input."""
        result = {"content": "", "metadata": {}}
        
        mime_type = input_data.mime_type or "application/octet-stream"
        file_name = input_data.file_name or "unknown"
        
        result["metadata"] = {
            "file_name": file_name,
            "file_size": input_data.file_size,
            "mime_type": mime_type,
            "category": self._categorize_file(mime_type).value
        }
        
        # Extract text content based on file type
        if mime_type in self.SUPPORTED_DOC_TYPES:
            content = await self._extract_document_content(
                input_data.content,
                mime_type
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
        self,
        content: Any,
        mime_type: str
    ) -> str:
        """Extract text content from document."""
        if mime_type == "text/plain" or mime_type == "text/csv":
            if isinstance(content, bytes):
                return content.decode("utf-8", errors="ignore")
            return str(content)
        
        # For other document types, use appropriate parsers
        # Simplified for now - in production, use proper document parsers
        return "[文档内容]"
    
    def validate_file(self, file_size: int, mime_type: str) -> Tuple[bool, str]:
        """
        Validate file size and type.
        
        Returns:
            (is_valid, error_message)
        """
        if mime_type in self.SUPPORTED_IMAGE_TYPES:
            if file_size > self.MAX_IMAGE_SIZE:
                return False, f"图片大小超过限制 ({self.MAX_IMAGE_SIZE / 1024 / 1024}MB)"
        elif mime_type in self.SUPPORTED_AUDIO_TYPES:
            if file_size > self.MAX_AUDIO_SIZE:
                return False, f"音频大小超过限制 ({self.MAX_AUDIO_SIZE / 1024 / 1024}MB)"
        else:
            if file_size > self.MAX_FILE_SIZE:
                return False, f"文件大小超过限制 ({self.MAX_FILE_SIZE / 1024 / 1024}MB)"
        
        return True, ""
    
    def format_for_llm(self, processed: ProcessedInput) -> List[Dict]:
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
                "image_url": {"url": url}
            })
        
        # Add file context
        if processed.file_contents:
            file_context = "\n".join([
                f"附件: {f['metadata'].get('file_name', 'unknown')}\n{f['content'][:500]}"
                for f in processed.file_contents
            ])
            parts.append({"type": "text", "text": f"\n[附件内容]\n{file_context}"})
        
        return parts


# Global instance
multimodal_service = MultimodalService()
