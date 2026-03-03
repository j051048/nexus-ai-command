"""
Web Search Helper — 供 VMD 工具内部调用的联网搜索辅助函数。

封装 Brave Search API 调用，返回格式化的搜索摘要文本，
可直接拼接到工具的 LLM prompt 中作为外部情报上下文。
"""

import logging
import time
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
_CACHE: dict[str, tuple[float, str]] = {}
_CACHE_TTL = 900  # 15 minutes


async def search_web(query: str, count: int = 5, freshness: str | None = None) -> str:
    """
    执行 Brave 搜索并返回格式化的摘要文本。

    Returns:
        格式化的搜索结果文本，失败时返回空字符串（不抛异常，不影响主流程）。
    """
    api_key = settings.BRAVE_SEARCH_API_KEY
    if not api_key or not query.strip():
        return ""

    cache_key = f"{query}:{count}:{freshness}"
    if cache_key in _CACHE:
        ts, cached = _CACHE[cache_key]
        if time.time() - ts < _CACHE_TTL:
            return cached

    params: dict[str, Any] = {
        "q": query,
        "count": min(max(count, 1), 10),
        "search_lang": "zh-hans",
        "text_decorations": False,
    }
    if freshness:
        params["freshness"] = freshness

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                _BRAVE_API_URL,
                params=params,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"Web search helper failed for '{query}': {e}")
        return ""

    web_results = data.get("web", {}).get("results", [])
    if not web_results:
        return ""

    lines = []
    for item in web_results:
        title = item.get("title", "")
        description = item.get("description", "")
        url = item.get("url", "")
        age = item.get("age", "")
        source_note = f" ({age})" if age else ""
        lines.append(f"- **{title}**{source_note}: {description} [{url}]")

    # Also include news
    news_results = data.get("news", {}).get("results", [])
    for item in news_results[:3]:
        title = item.get("title", "")
        description = item.get("description", "")
        age = item.get("age", "")
        lines.append(f"- 📰 **{title}** ({age}): {description}")

    result = "\n".join(lines)
    _CACHE[cache_key] = (time.time(), result)
    return result
