"""
文件管理系统
支持文件上传、下载、解析
"""
import logging
from typing import Any, Literal

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
async def upload_file(
    file_content: str,
    filename: str,
    org_id: str,
    file_type: Literal["contract", "tender", "document", "other"] = "document",
) -> dict[str, Any]:
    """上传文件到存储

    Args:
        file_content: 文件内容（base64编码）
        filename: 文件名
        org_id: 组织ID
        file_type: 文件类型

    Returns:
        包含文件URL和ID的字典
    """
    try:
        import base64
        from datetime import datetime

        from app.core.database import supabase

        # 解码文件内容
        file_bytes = base64.b64decode(file_content)

        # 生成存储路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        storage_path = f"{org_id}/{file_type}/{timestamp}_{filename}"

        # 上传到 Supabase Storage
        await supabase.storage.from_("documents").upload(
            storage_path, file_bytes, {"content-type": "application/octet-stream"}
        )

        # 获取公开URL
        file_url = supabase.storage.from_("documents").get_public_url(storage_path)

        # 记录到数据库
        file_record = await supabase.table("file_uploads").insert({
            "org_id": org_id,
            "filename": filename,
            "file_type": file_type,
            "storage_path": storage_path,
            "file_url": file_url,
        }).execute()

        return {
            "success": True,
            "file_id": file_record.data[0]["id"],
            "file_url": file_url,
            "storage_path": storage_path,
        }

    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        return {"success": False, "error": str(e)}


@tool
async def parse_file(
    file_id: str,
    org_id: str,
) -> dict[str, Any]:
    """解析文件内容（PDF/Word/Excel）

    Args:
        file_id: 文件ID
        org_id: 组织ID

    Returns:
        包含解析后文本内容的字典
    """
    try:
        from app.core.database import supabase

        # 获取文件信息
        file_info = await supabase.table("file_uploads").select("*").eq("id", file_id).eq("org_id", org_id).single().execute()

        if not file_info.data:
            return {"success": False, "error": "文件不存在"}

        storage_path = file_info.data["storage_path"]
        filename = file_info.data["filename"]

        # 下载文件
        file_bytes = await supabase.storage.from_("documents").download(storage_path)

        # 根据文件类型解析
        text_content = ""
        if filename.endswith(".pdf"):
            text_content = _parse_pdf(file_bytes)
        elif filename.endswith((".doc", ".docx")):
            text_content = _parse_word(file_bytes)
        elif filename.endswith((".xls", ".xlsx")):
            text_content = _parse_excel(file_bytes)
        else:
            return {"success": False, "error": "不支持的文件格式"}

        return {
            "success": True,
            "file_id": file_id,
            "filename": filename,
            "content": text_content[:10000],  # 限制长度
            "length": len(text_content),
        }

    except Exception as e:
        logger.error(f"文件解析失败: {e}")
        return {"success": False, "error": str(e)}


def _parse_pdf(file_bytes: bytes) -> str:
    """解析PDF"""
    try:
        import io

        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        return "\n".join(page.extract_text() for page in reader.pages)
    except Exception:
        return ""


def _parse_word(file_bytes: bytes) -> str:
    """解析Word"""
    try:
        import io

        import docx
        doc = docx.Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return ""


def _parse_excel(file_bytes: bytes) -> str:
    """解析Excel"""
    try:
        import io

        import pandas as pd
        df = pd.read_excel(io.BytesIO(file_bytes))
        return df.to_string()
    except Exception:
        return ""

