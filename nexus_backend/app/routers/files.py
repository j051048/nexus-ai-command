"""
文件管理路由
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import get_current_org_id, get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.tools.file_manager import parse_file, upload_file

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/files", tags=["files"])


class UploadRequest(BaseModel):
    file_content: str
    filename: str
    file_type: str = "document"


class ParseRequest(BaseModel):
    file_id: str


@router.post("/upload")
async def upload(
    request: UploadRequest,
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    """上传文件"""
    try:
        result = await upload_file(
            file_content=request.file_content,
            filename=request.filename,
            org_id=org_id,
            file_type=request.file_type,
        )
        return (
            api_success(result)
            if result.get("success")
            else api_error(result.get("error"))
        )
    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "文件上传失败，请稍后重试")


@router.post("/parse")
async def parse(
    request: ParseRequest,
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    """解析文件"""
    try:
        result = await parse_file(file_id=request.file_id, org_id=org_id)
        return (
            api_success(result)
            if result.get("success")
            else api_error(result.get("error"))
        )
    except Exception as e:
        logger.error(f"文件解析失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "文件解析失败，请稍后重试")
