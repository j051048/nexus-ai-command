"""
P3: 聊天图片上传端点。
接收图片文件，base64 编码存储到 chat_attachments 表，返回 data URI。
与 RAG 知识库管线完全隔离（不触碰 documents/document_embeddings 表）。
"""

import base64
import logging

from fastapi import APIRouter, Depends, File, Request, UploadFile

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Chat"])

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/upload-image")
async def upload_chat_image(
    req: Request,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """Upload an image for use in chat (e.g., invoice OCR). NOT indexed into RAG."""

    # 1. Validate MIME type
    content_type = file.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        return api_error(
            ErrorCode.VALIDATION_ERROR,
            f"不支持的图片格式: {content_type}。支持 JPEG/PNG/WebP/GIF。",
        )

    # 2. Read and validate size
    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        return api_error(
            ErrorCode.VALIDATION_ERROR,
            f"图片大小 {len(content) / 1024 / 1024:.1f}MB 超过限制 (最大 10MB)。",
        )

    # 3. Base64 encode
    b64_data = base64.b64encode(content).decode("utf-8")
    data_uri = f"data:{content_type};base64,{b64_data}"

    # 4. Persist to chat_attachments (NOT documents table)
    client = req.state.db
    try:
        result = await client.table("chat_attachments").insert({
            "user_id": user_id,
            "filename": file.filename or "image",
            "mime_type": content_type,
            "base64_data": b64_data,
            "size_bytes": len(content),
        }).execute()

        attachment_id = result.data[0]["id"] if result.data else None
    except Exception as e:
        logger.warning(f"chat_attachments insert failed (table may not exist yet): {e}")
        attachment_id = None

    logger.info(f"[ChatUpload] user={user_id} file={file.filename} size={len(content)} type={content_type}")

    return api_success(
        data={
            "url": data_uri,
            "attachment_id": attachment_id,
            "filename": file.filename,
            "size_bytes": len(content),
        },
        message="图片上传成功",
    )
