"""
数据导入路由 - 批量导入员工和客户数据
提供文件上传、模板下载、数据预览等功能
"""

from fastapi import APIRouter, UploadFile, File, Depends, Request
from fastapi.responses import PlainTextResponse
from app.core.auth import get_current_user_id
from app.core.errors import api_success, api_error, ErrorCode
from app.services.import_service import ImportService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import", tags=["Import"])

# 文件大小限制（10MB）
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def validate_file(file: UploadFile) -> None:
    """
    验证上传文件的类型和大小

    Args:
        file: 上传的文件对象

    Raises:
        HTTPException: 文件验证失败
    """
    # 检查文件扩展名
    filename = file.filename or ""
    file_ext = "." + filename.lower().split(".")[-1] if "." in filename else ""

    if file_ext not in ALLOWED_EXTENSIONS:
        raise api_error(
            ErrorCode.VALIDATION_ERROR,
            f"不支持的文件类型: {file_ext}，仅支持 .csv, .xlsx, .xls",
        )


@router.post("/employees")
async def import_employees(
    request: Request,
    file: UploadFile = File(...),
    mode: str = "insert",
    user_id: str = Depends(get_current_user_id),
):
    """
    批量导入员工数据

    - 支持 CSV 和 Excel 格式
    - 自动跳过已存在的邮箱
    - 返回导入结果统计
    - mode: insert（默认）或 incremental（增量更新）
    """
    validate_file(file)

    # 读取文件内容
    contents = await file.read()

    # 检查文件大小
    if len(contents) > MAX_FILE_SIZE:
        raise api_error(ErrorCode.VALIDATION_ERROR, "文件大小超过限制（最大 10MB）")

    # 获取数据库客户端（支持 RLS）
    db_client = request.state.db
    if not db_client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    try:
        # 执行导入
        result = await ImportService.import_employees(
            contents=contents,
            filename=file.filename or "unknown.csv",
            user_id=user_id,
            db_client=db_client,
            mode=mode,
        )

        logger.info(
            f"员工导入完成 - 用户: {user_id}, 模式: {mode}, "
            f"成功: {result['success_count']}, "
            f"跳过: {result['skip_count']}, "
            f"失败: {result['error_count']}"
        )

        return api_success(data=result)

    except Exception as e:
        logger.error(f"员工导入失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, f"导入失败: {str(e)}")


@router.post("/customers")
async def import_customers(
    request: Request,
    file: UploadFile = File(...),
    mode: str = "insert",
    user_id: str = Depends(get_current_user_id),
):
    """
    批量导入客户数据

    - 支持 CSV 和 Excel 格式
    - 自动跳过已存在的客户（按名称+公司判断）
    - 返回导入结果统计
    - mode: insert（默认）或 incremental（增量更新）
    """
    validate_file(file)

    # 读取文件内容
    contents = await file.read()

    # 检查文件大小
    if len(contents) > MAX_FILE_SIZE:
        raise api_error(ErrorCode.VALIDATION_ERROR, "文件大小超过限制（最大 10MB）")

    # 获取数据库客户端（支持 RLS）
    db_client = request.state.db
    if not db_client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    try:
        # 执行导入
        result = await ImportService.import_customers(
            contents=contents,
            filename=file.filename or "unknown.csv",
            user_id=user_id,
            db_client=db_client,
            mode=mode,
        )

        logger.info(
            f"客户导入完成 - 用户: {user_id}, 模式: {mode}, "
            f"成功: {result['success_count']}, "
            f"跳过: {result['skip_count']}, "
            f"失败: {result['error_count']}"
        )

        return api_success(data=result)

    except Exception as e:
        logger.error(f"客户导入失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, f"导入失败: {str(e)}")


@router.get("/templates/{template_type}")
async def get_import_template(
    template_type: str, user_id: str = Depends(get_current_user_id)
):
    """
    下载导入模板（CSV 格式）

    支持的模板类型:
    - employees: 员工导入模板
    - customers: 客户导入模板
    """
    try:
        template_content = ImportService.get_template(template_type)

        # 返回纯文本 CSV 内容
        return PlainTextResponse(
            content=template_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={template_type}_template.csv"
            },
        )

    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_ERROR, str(e))
    except Exception as e:
        logger.error(f"获取模板失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, f"获取模板失败: {str(e)}")


@router.post("/preview")
async def preview_import_data(
    file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)
):
    """
    预览导入数据

    - 解析文件并返回前10行数据
    - 返回总行数统计
    - 不实际导入数据
    """
    validate_file(file)

    # 读取文件内容
    contents = await file.read()

    # 检查文件大小
    if len(contents) > MAX_FILE_SIZE:
        raise api_error(ErrorCode.VALIDATION_ERROR, "文件大小超过限制（最大 10MB）")

    try:
        # 预览数据
        preview_data = await ImportService.preview(
            contents=contents, filename=file.filename or "unknown.csv"
        )

        return api_success(data=preview_data)

    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_ERROR, str(e))
    except Exception as e:
        logger.error(f"预览数据失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, f"预览失败: {str(e)}")
