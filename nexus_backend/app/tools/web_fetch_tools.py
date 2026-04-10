"""
WebFetch 工具 — 抓取指定 URL 的网页内容并返回纯文本摘要。

安全限制：禁止访问内网地址。
"""

import contextlib
import logging
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

from app.tools._shared import safe_tool_error

from .base_tool import BaseTool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 内网地址检测
# ---------------------------------------------------------------------------
_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]"}
_PRIVATE_RE = re.compile(
    r"^(10\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    r"|(172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})"
    r"|(192\.168\.\d{1,3}\.\d{1,3})$"
)


def _is_private_url(url: str) -> bool:
    """检查 URL 是否指向内网地址。"""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if host in _BLOCKED_HOSTS:
            return True
        if _PRIVATE_RE.match(host):
            return True
    except Exception:
        return True
    return False


# ---------------------------------------------------------------------------
# 简易 HTML → 纯文本
# ---------------------------------------------------------------------------
class _TextExtractor(HTMLParser):
    """从 HTML 中提取纯文本，跳过 script / style 标签内容。"""

    _SKIP_TAGS = {"script", "style", "noscript"}

    def __init__(self):
        super().__init__()
        self._pieces: list[str] = []
        self._skip_depth = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str):
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str):
        if self._in_title:
            self.title += data.strip()
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._pieces.append(text)

    def get_text(self) -> str:
        return "\n".join(self._pieces)


def _html_to_text(html: str) -> tuple[str, str]:
    """返回 (title, body_text)。"""
    extractor = _TextExtractor()
    with contextlib.suppress(Exception):
        extractor.feed(html)
    return extractor.title, extractor.get_text()


# ---------------------------------------------------------------------------
# 工具类
# ---------------------------------------------------------------------------
class WebFetchTool(BaseTool):
    """抓取指定 URL 的网页内容并返回纯文本摘要。"""

    name = "web_fetch"
    description = (
        "抓取指定网址的网页内容并返回纯文本摘要，支持自定义最大返回长度。"
        "当用户需要查看某个网页内容或获取在线资料时调用。"
    )
    domain = "knowledge"
    examples = [
        {
            "input": {"url": "https://example.com/article/123"},
            "output_summary": "抓取该网页并返回标题和正文纯文本（默认最多2000字符）",
        },
        {
            "input": {"url": "https://example.com/report.html", "max_length": 5000},
            "output_summary": "抓取网页并返回最多5000字符的纯文本内容",
        },
    ]
    related_tools = ["web_search"]
    gotchas = "禁止访问内网地址（会被安全拦截）；网址必须以 http:// 或 https:// 开头；max_length 范围 100-10000，超出自动截断。"

    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "要抓取的网页 URL（必填，需以 http:// 或 https:// 开头）",
            },
            "max_length": {
                "type": "integer",
                "description": "返回内容的最大字符数，默认 2000",
            },
        },
        "required": ["url"],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        import json

        url = (args.get("url") or "").strip()
        max_length = args.get("max_length", 2000)

        # --- 参数校验 ---
        if not url:
            return "请提供要抓取的 URL。"
        if not url.startswith(("http://", "https://")):
            return "URL 必须以 http:// 或 https:// 开头。"

        try:
            max_length = max(100, min(int(max_length), 10000))
        except (TypeError, ValueError):
            max_length = 2000

        # --- 安全检查 ---
        if _is_private_url(url):
            return "出于安全限制，不允许访问内网地址。"

        # --- 抓取 ---
        try:
            import httpx

            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=10.0,
                headers={"User-Agent": "NexusBot/1.0"},
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
        except Exception as e:
            return safe_tool_error(e, "抓取")

        # --- 解析 ---
        title, text = _html_to_text(html)
        if not text:
            text = "(页面未提取到有效文本内容)"

        truncated = text[:max_length]

        result = {
            "url": url,
            "title": title or "(无标题)",
            "content": truncated,
            "content_length": len(truncated),
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
