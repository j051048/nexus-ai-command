"""
数据导出路由
支持 Excel/PDF 导出
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.tools.export_tools import export_to_excel, export_to_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/export", tags=["export"])


class ExportExcelRequest(BaseModel):
    data: list[dict[str, Any]] = Field(..., description="要导出的数据")
    filename: str = Field(default="", description="文件名")
    sheet_name: str = Field(default="Sheet1", description="工作表名称")
    include_header: bool = Field(default=True, description="是否包含表头")


class ExportPDFRequest(BaseModel):
    content: str = Field(..., description="要导出的内容")
    filename: str = Field(default="", description="文件名")
    title: str = Field(default="", description="文档标题")
    format_type: str = Field(default="markdown", description="内容格式")


@router.post("/excel")
async def export_excel(
    request: ExportExcelRequest,
    user_id: str = Depends(get_current_user_id),
):
    """导出 Excel 文件"""
    try:
        result = await export_to_excel(
            data=request.data,
            filename=request.filename,
            sheet_name=request.sheet_name,
            include_header=request.include_header,
        )

        if not result.get("success"):
            return api_error(result.get("error", "导出失败"))

        return api_success(result)

    except Exception as e:
        logger.error(f"Excel 导出失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "Excel 导出失败，请稍后重试")


@router.post("/pdf")
async def export_pdf(
    request: ExportPDFRequest,
    user_id: str = Depends(get_current_user_id),
):
    """导出 PDF 文件"""
    try:
        result = await export_to_pdf(
            content=request.content,
            filename=request.filename,
            title=request.title,
            format_type=request.format_type,
        )

        if not result.get("success"):
            return api_error(result.get("error", "导出失败"))

        return api_success(result)

    except Exception as e:
        logger.error(f"PDF 导出失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "PDF 导出失败，请稍后重试")
