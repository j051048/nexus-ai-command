"""
Item 11: API Docs Router
API 文档增强端点 - 提供增强版 OpenAPI spec 和端点信息。
"""

import logging
from fastapi import APIRouter, Depends, Request
from app.core.auth import get_current_user_id
from app.core.errors import api_success, api_error, ErrorCode
from app.core.api_docs import (
    API_TAGS_METADATA,
    API_VERSION,
    API_CHANGELOG,
    SWAGGER_UI_CONFIG,
    get_enhanced_openapi_description,
    get_endpoint_stats,
    get_all_examples,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/docs", tags=["API Docs"])


@router.get("/openapi-enhanced")
async def get_enhanced_openapi(request: Request):
    """
    获取增强版 OpenAPI 规范。

    包含:
    - 中英文描述
    - 详细的标签分组描述
    - 请求/响应示例
    - 端点统计信息

    此端点无需认证。
    """
    try:
        # 获取原始 OpenAPI schema
        openapi_schema = request.app.openapi()

        # 增强描述
        enhanced = dict(openapi_schema)
        enhanced["info"] = {
            **enhanced.get("info", {}),
            "description": get_enhanced_openapi_description(),
            "version": API_VERSION,
            "x-api-changelog": API_CHANGELOG,
        }

        # 增强标签
        enhanced["tags"] = API_TAGS_METADATA

        # 添加 Swagger UI 配置
        enhanced["x-swagger-ui-config"] = SWAGGER_UI_CONFIG

        # 添加端点统计
        enhanced["x-endpoint-stats"] = get_endpoint_stats(request.app)

        return enhanced

    except Exception as e:
        logger.error(f"Error generating enhanced OpenAPI: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/stats")
async def get_api_stats(request: Request):
    """
    获取 API 端点统计信息。

    返回路由总数、HTTP 方法分布、标签分组统计。
    """
    try:
        stats = get_endpoint_stats(request.app)

        return api_success(
            data={
                "version": API_VERSION,
                "stats": stats,
            }
        )

    except Exception as e:
        logger.error(f"Error getting API stats: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/examples")
async def get_api_examples():
    """
    获取 API 请求/响应示例集合。

    返回主要端点的请求体和响应体示例，方便前端开发和集成测试。
    """
    try:
        examples = get_all_examples()

        return api_success(data=examples)

    except Exception as e:
        logger.error(f"Error getting API examples: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/changelog")
async def get_api_changelog():
    """
    获取 API 变更日志。

    返回各版本的功能变更记录。
    """
    try:
        return api_success(
            data={
                "current_version": API_VERSION,
                "changelog": API_CHANGELOG,
            }
        )

    except Exception as e:
        logger.error(f"Error getting API changelog: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/tags")
async def get_api_tags():
    """
    获取 API 标签分组及其描述。

    返回所有 API 分组的名称和详细描述。
    """
    try:
        return api_success(
            data={
                "tags": API_TAGS_METADATA,
                "total": len(API_TAGS_METADATA),
            }
        )

    except Exception as e:
        logger.error(f"Error getting API tags: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
