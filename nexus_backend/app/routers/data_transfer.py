"""
Item 8: Data Transfer Router
数据导入/导出统一 API 端点。
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.data_export_service import data_export_service
from app.services.data_import_service import data_import_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data", tags=["Data Transfer"])

# 文件大小限制
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


# ============== Request Models ==============


class ExportRequest(BaseModel):
    """导出请求体"""

    filters: dict[str, Any] | None = Field(None, description="过滤条件")
    date_from: str | None = Field(None, description="开始日期 (YYYY-MM-DD)")
    date_to: str | None = Field(None, description="结束日期 (YYYY-MM-DD)")


class ImportValidateRequest(BaseModel):
    """导入预验证请求体"""

    import_type: str = Field(..., description="导入类型")
    csv_content: str = Field(..., description="CSV 字符串内容")
    column_mapping: dict[str, str] | None = Field(None, description="自定义列映射 (原列名 -> 标准列名)")


# ============== Export Endpoints ==============


@router.post("/export/{export_type}")
async def export_data(
    request: Request,
    export_type: str,
    body: ExportRequest = ExportRequest(),
    user_id: str = Depends(get_current_user_id),
    format: str = Query("csv", description="导出格式: csv 或 xlsx"),
):
    """
    导出数据为 CSV 或 Excel。

    支持的导出类型:
    - approvals: 审批记录
    - attendance: 考勤数据
    - sales: 销售数据
    - employees: 员工数据
    - customers: 客户数据

    参数 format=csv|xlsx 控制输出格式。
    """
    org_id = getattr(request.state, "org_id", None)
    db = getattr(request.state, "db", None)

    if format not in ("csv", "xlsx"):
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "format 参数只支持 csv 或 xlsx")

    try:
        # 构建过滤条件
        filters = body.filters or {}
        if body.date_from:
            filters["date_from"] = body.date_from
        if body.date_to:
            filters["date_to"] = body.date_to

        if format == "xlsx":
            # Excel 导出（通用路径）
            xlsx_bytes = await data_export_service.export_to_xlsx(
                export_type=export_type,
                filters=filters,
                org_id=org_id,
                db=db,
            )
            filename = f"{export_type}_export.xlsx"
            return Response(
                content=xlsx_bytes,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )

        # CSV 导出（保持原有逻辑）
        if export_type == "approvals" and org_id:
            csv_content = await data_export_service.export_approvals(org_id=org_id, filters=filters, db=db)
        elif export_type == "attendance" and org_id:
            date_range = {}
            if body.date_from:
                date_range["from"] = body.date_from
            if body.date_to:
                date_range["to"] = body.date_to
            csv_content = await data_export_service.export_attendance(
                org_id=org_id, date_range=date_range or None, db=db
            )
        elif export_type == "sales" and org_id:
            csv_content = await data_export_service.export_sales_data(org_id=org_id, filters=filters, db=db)
        else:
            # 通用导出
            csv_content = await data_export_service.export_to_csv(
                export_type=export_type,
                filters=filters,
                org_id=org_id,
                db=db,
            )

        filename = f"{export_type}_export.csv"

        return PlainTextResponse(
            content=csv_content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
            },
        )

    except ValueError:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "数据传输参数校验失败")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Export {export_type} failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "导出失败")


@router.get("/export/types")
async def list_export_types(
    user_id: str = Depends(get_current_user_id),
):
    """获取所有可用的导出类型及其列信息。"""
    try:
        exports = data_export_service.get_available_exports()
        return api_success(data=exports)
    except Exception as e:
        logger.error(f"List export types failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据传输操作失败")


# ============== Template Endpoints ==============


@router.get("/templates")
async def list_templates(
    user_id: str = Depends(get_current_user_id),
):
    """获取所有可用的导入模板列表。"""
    try:
        templates = data_export_service.get_available_templates()
        return api_success(data=templates)
    except Exception as e:
        logger.error(f"List templates failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据传输操作失败")


@router.get("/templates/{template_type}")
async def download_template(
    template_type: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    下载导入模板 CSV。

    支持的模板类型:
    - employees: 员工导入模板
    - customers: 客户导入模板
    - attendance: 考勤导入模板
    - sales: 销售数据导入模板
    """
    try:
        csv_content = data_export_service.generate_template(template_type)

        return PlainTextResponse(
            content=csv_content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename={template_type}_template.csv",
            },
        )

    except ValueError:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "数据传输参数校验失败")
    except Exception as e:
        logger.error(f"Download template {template_type} failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据传输操作失败")


# ============== Import Endpoints ==============


@router.post("/import/{import_type}")
async def import_data(
    request: Request,
    import_type: str,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """
    导入 CSV 数据。

    支持的导入类型:
    - employees: 员工数据
    - customers: 客户数据
    - attendance: 考勤数据
    - sales: 销售数据

    文件要求:
    - 格式: CSV
    - 编码: UTF-8 (推荐) 或 GBK
    - 最大: 10MB
    - 第一行必须是表头
    """
    org_id = getattr(request.state, "org_id", None)
    db = getattr(request.state, "db", None)

    if not org_id:
        raise api_error(ErrorCode.VALIDATION_MISSING_FIELD, "需要组织上下文")

    # 验证文件
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise api_error(
            ErrorCode.VALIDATION_INVALID_INPUT,
            "仅支持 CSV 格式文件",
        )

    try:
        contents = await file.read()

        if len(contents) > MAX_FILE_SIZE:
            raise api_error(
                ErrorCode.VALIDATION_INVALID_INPUT,
                "文件大小超过限制（最大 10MB）",
            )

        # 尝试 UTF-8 解码，失败则用 GBK
        try:
            csv_content = contents.decode("utf-8")
        except UnicodeDecodeError:
            try:
                csv_content = contents.decode("gbk")
            except UnicodeDecodeError:
                raise api_error(
                    ErrorCode.VALIDATION_INVALID_INPUT,
                    "无法识别文件编码，请使用 UTF-8 或 GBK",
                )

        result = await data_import_service.import_csv(
            import_type=import_type,
            csv_content=csv_content,
            org_id=org_id,
            user_id=user_id,
            db=db,
        )

        logger.info(
            f"Data import completed: type={import_type}, user={user_id}, "
            f"success={result['success_count']}, errors={result['error_count']}"
        )

        return api_success(data=result)

    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Import {import_type} failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "导入失败")


@router.post("/import/validate")
async def validate_import(
    body: ImportValidateRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    预验证导入数据（不实际写入数据库）。

    提交 CSV 内容进行格式和数据验证，返回:
    - 是否全部有效
    - 有效行数/错误行数
    - 具体的错误信息
    - 前5行有效数据预览
    """
    try:
        result = await data_import_service.validate_import_data(
            import_type=body.import_type,
            csv_content=body.csv_content,
            column_mapping=body.column_mapping,
        )

        return api_success(data=result)

    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Validate import failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据传输操作失败")
