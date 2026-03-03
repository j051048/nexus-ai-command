"""
招投标数据查询服务

封装 APISpace 的招投标数据查询 API，提供：
- 列表查询 (project-list)
- 详情查询 (detail)
- 结构化数据查询 (structre-detail)
"""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://23330.o.apispace.com/project-info-upgrade"
_REQUEST_TIMEOUT = 20.0  # seconds


def _get_token() -> str:
    """从配置中获取 APISpace Token"""
    token = getattr(settings, "APISPACE_BIDDING_TOKEN", None) or ""
    if not token:
        raise ValueError("未配置 APISPACE_BIDDING_TOKEN 环境变量")
    return token


def _headers(content_type: str = "application/json") -> dict[str, str]:
    return {
        "X-APISpace-Token": _get_token(),
        "Content-Type": content_type,
    }


async def search_projects(
    keyword: str,
    start_date: str | None = None,
    end_date: str | None = None,
    page_size: int = 20,
    page: int = 1,
    search_type: str = "1",
    class_id: str = "-100",
) -> dict[str, Any]:
    """
    搜索招投标项目列表

    Args:
        keyword: 搜索关键词
        start_date: 开始日期 (yyyy-MM-dd)，默认近30天
        end_date: 结束日期 (yyyy-MM-dd)，默认今天
        page_size: 每页记录数 (最大100)
        page: 页码
        search_type: 1(智能/模糊), 2(精准), 3(高级)
        class_id: 项目分类ID，-100为全部

    Returns:
        {"status": "success", "total": int, "projects": list}
        或 {"status": "error", "message": str}
    """
    from datetime import datetime, timedelta

    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    payload = {
        "keyword": keyword,
        "searchMode": "1",  # 1: 全部(标题+内容)
        "startDate": start_date,
        "endDate": end_date,
        "userID": "2",
        "pageID": str(page),
        "pageNumber": str(min(page_size, 100)),
        "searchType": search_type,
        "classID": class_id,
        "excludeKW": "",
        "inCludeKW": "",
        "proviceCodeList": ["0"],
        "cityCodeList": [],
        "countyCodeList": [],
        "firstCodeList": ["0"],
        "secondCodeLis": [],
        "thirdCodeList": [],
        "purchaseTypeID": "-100",
    }

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{_BASE_URL}/project-list",
                json=payload,
                headers=_headers(),
            )
            response.raise_for_status()
            data = response.json()

            if str(data.get("code")) == "200" and data.get("data"):
                return {
                    "status": "success",
                    "total": data["data"].get("total", 0),
                    "projects": data["data"].get("data", []),
                }
            else:
                msg = data.get("msg", "Unknown error")
                logger.error(f"Bidding API list error: {msg}")
                return {"status": "error", "message": msg}
    except Exception as e:
        logger.error(f"Bidding API list exception: {e}")
        return {"status": "error", "message": str(e)}


async def get_project_detail(project_id: str, publish_time: str) -> dict[str, Any]:
    """
    获取项目的详细长文本正文

    Args:
        project_id: 项目 ID
        publish_time: 发布时间 (yyyy-MM-dd HH:mm:ss)
    """
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{_BASE_URL}/detail",
                data={"id": project_id, "publishTime": publish_time},
                headers=_headers("application/x-www-form-urlencoded"),
            )
            response.raise_for_status()
            data = response.json()

            if str(data.get("code")) == "200":
                return {"status": "success", "detail": data.get("data", {})}
            else:
                return {"status": "error", "message": data.get("msg", "Error")}
    except Exception as e:
        logger.error(f"Bidding API detail exception: {e}")
        return {"status": "error", "message": str(e)}


async def get_structured_detail(project_id: str, publish_time: str) -> dict[str, Any]:
    """获取项目的结构化提取数据"""
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{_BASE_URL}/structre-detail",
                data={"id": project_id, "publishTime": publish_time},
                headers=_headers("application/x-www-form-urlencoded"),
            )
            response.raise_for_status()
            data = response.json()

            if str(data.get("code")) == "200":
                return {"status": "success", "structured_data": data.get("data", {})}
            else:
                return {"status": "error", "message": data.get("msg", "Error")}
    except Exception as e:
        logger.error(f"Bidding API struct exception: {e}")
        return {"status": "error", "message": str(e)}
