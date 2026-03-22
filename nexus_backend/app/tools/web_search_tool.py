"""
Web Search Tool — 联网搜索能力 (Brave Search API)

为 AI Agent 提供实时互联网搜索能力，用于：
- 竞品最新动态查询
- 行业趋势和新闻搜索
- 市场数据和公开信息检索
- 技术标准和政策法规查询
"""

import logging
from typing import Any

import httpx

from app.core.config import settings

from .base_tool import BaseTool

logger = logging.getLogger(__name__)

_BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
_CACHE: dict[str, tuple[float, str]] = {}  # query -> (timestamp, result)
_CACHE_TTL = 900  # 15 minutes


class WebSearchTool(BaseTool):
    """搜索互联网获取实时信息"""

    name = "web_search"
    description = (
        "搜索互联网获取实时公开信息，包括行业新闻、竞品动态、市场数据、政策法规等。"
        "当需要最新外部信息或知识库中未覆盖的公开数据时调用。"
        "不要用于查询内部业务数据（客户、合同等），请用对应的专用工具。"
        "招投标信息请使用专用的搜索工具，不要用本工具搜索。"
    )
    required_role = "all"
    examples = [
        {"input": {"query": "2026年中国光伏行业趋势", "count": 5}, "output_summary": "返回5条关于光伏行业趋势的最新搜索结果"},
        {"input": {"query": "华为最新产品发布", "freshness": "pw"}, "output_summary": "返回过去一周内华为产品发布的相关信息"},
    ]
    gotchas = "仅用于需要实时外部信息的查询（如行业动态、竞品信息）；内部数据查询请用对应业务工具；需配置环境变量中的搜索服务密钥。"
    related_tools = ["load_knowledge", "web_fetch"]

    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词（建议用中文或英文，简洁精准）",
            },
            "count": {
                "type": "integer",
                "description": "返回结果数量（1-10，默认5）",
            },
            "freshness": {
                "type": "string",
                "enum": ["pd", "pw", "pm", "py"],
                "description": "时效过滤: pd=过去24小时, pw=过去一周, pm=过去一月, py=过去一年",
            },
        },
        "required": ["query"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        query = args.get("query", "").strip()
        if not query:
            return "❌ 请提供搜索关键词。"

        count = min(max(args.get("count", 5), 1), 10)
        freshness = args.get("freshness")

        api_key = settings.BRAVE_SEARCH_API_KEY
        if not api_key:
            return "❌ 未配置 Brave Search API Key，无法执行联网搜索。请在环境变量中设置 BRAVE_SEARCH_API_KEY。"

        # Check cache
        import time

        cache_key = f"{query}:{count}:{freshness}"
        if cache_key in _CACHE:
            ts, cached = _CACHE[cache_key]
            if time.time() - ts < _CACHE_TTL:
                return cached

        # Call Brave Search API
        params: dict[str, Any] = {
            "q": query,
            "count": count,
            "search_lang": "zh-hans",
            "text_decorations": False,
        }
        if freshness:
            params["freshness"] = freshness

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
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
        except httpx.TimeoutException:
            return "❌ 搜索超时，请稍后重试。"
        except httpx.HTTPStatusError as e:
            logger.error(f"Brave Search API error: {e.response.status_code} {e.response.text[:200]}")
            return f"❌ 搜索服务异常（HTTP {e.response.status_code}），请稍后重试。"
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return f"❌ 搜索失败: {str(e)}"

        # Parse results
        web_results = data.get("web", {}).get("results", [])
        if not web_results:
            return f'🔍 搜索 "{query}" 未找到相关结果。'

        lines = [f'🔍 **搜索结果 — "{query}"**（共 {len(web_results)} 条）\n']

        for i, item in enumerate(web_results, 1):
            title = item.get("title", "无标题")
            url = item.get("url", "")
            description = item.get("description", "无摘要")
            age = item.get("age", "")

            lines.append(f"### {i}. {title}")
            if age:
                lines.append(f"📅 {age}")
            lines.append(f"{description}")
            lines.append(f"🔗 {url}\n")

        # Also include news if available
        news_results = data.get("news", {}).get("results", [])
        if news_results:
            lines.append("---\n📰 **相关新闻**\n")
            for item in news_results[:3]:
                title = item.get("title", "")
                url = item.get("url", "")
                age = item.get("age", "")
                lines.append(f"- **{title}** {f'({age})' if age else ''} — {url}")

        result = "\n".join(lines)

        # Update cache
        _CACHE[cache_key] = (time.time(), result)

        return result
