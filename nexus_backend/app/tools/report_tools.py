"""
ReportGenerator 工具 — 将数据生成为格式化的 Markdown / HTML 报告。
"""

import json
import logging
from datetime import datetime
from html import escape as html_escape
from typing import Any

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Markdown 生成
# ---------------------------------------------------------------------------


def _build_markdown_table(table_data: list[dict]) -> str:
    """从 list[dict] 生成 Markdown 表格。"""
    if not table_data:
        return ""
    headers = list(table_data[0].keys())
    lines = [
        "| " + " | ".join(str(h) for h in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in table_data:
        cells = [str(row.get(h, "")) for h in headers]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _build_markdown(title: str, sections: list[dict]) -> str:
    """组装 Markdown 文档。"""
    parts = [f"# {title}\n"]

    for sec in sections:
        heading = sec.get("heading", "")
        content = sec.get("content", "")
        table_data = sec.get("table_data")

        if heading:
            parts.append(f"## {heading}\n")
        if content:
            parts.append(f"{content}\n")
        if table_data and isinstance(table_data, list) and len(table_data) > 0:
            parts.append(_build_markdown_table(table_data))
            parts.append("")  # 空行

    # 时间戳
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts.append(f"\n---\n*报告生成时间: {now}*")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Markdown → 简易 HTML
# ---------------------------------------------------------------------------


def _md_to_simple_html(md: str) -> str:
    """将 Markdown 转为简单 HTML（仅覆盖标题、段落、表格、分割线、斜体）。"""
    html_lines = [
        "<!DOCTYPE html>",
        '<html lang="zh"><head><meta charset="utf-8">',
        "<style>body{font-family:sans-serif;max-width:800px;margin:0 auto;padding:20px}"
        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #ddd;padding:8px;text-align:left}"
        "th{background:#f5f5f5}hr{margin:20px 0}</style></head><body>",
    ]

    in_table = False
    for line in md.split("\n"):
        stripped = line.strip()

        # 分割线
        if stripped == "---":
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append("<hr>")
            continue

        # 标题
        if stripped.startswith("# "):
            level = 0
            for ch in stripped:
                if ch == "#":
                    level += 1
                else:
                    break
            level = min(level, 6)
            text = html_escape(stripped[level:].strip())
            html_lines.append(f"<h{level}>{text}</h{level}>")
            continue

        # 表格行
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            # 跳过分隔行
            if all(c.replace("-", "").strip() == "" for c in cells):
                continue
            if not in_table:
                html_lines.append("<table><thead><tr>")
                for c in cells:
                    html_lines.append(f"<th>{html_escape(c)}</th>")
                html_lines.append("</tr></thead><tbody>")
                in_table = True
            else:
                html_lines.append("<tr>")
                for c in cells:
                    html_lines.append(f"<td>{html_escape(c)}</td>")
                html_lines.append("</tr>")
            continue

        # 关闭表格
        if in_table:
            html_lines.append("</tbody></table>")
            in_table = False

        # 斜体 *text*
        if stripped.startswith("*") and stripped.endswith("*") and len(stripped) > 2:
            html_lines.append(f"<p><em>{html_escape(stripped[1:-1])}</em></p>")
            continue

        # 普通段落
        if stripped:
            html_lines.append(f"<p>{html_escape(stripped)}</p>")

    if in_table:
        html_lines.append("</tbody></table>")

    html_lines.append("</body></html>")
    return "\n".join(html_lines)


# ---------------------------------------------------------------------------
# 工具类
# ---------------------------------------------------------------------------
class ReportGeneratorTool(BaseTool):
    """将数据生成为格式化的 Markdown / HTML 报告。"""

    name = "generate_report"
    description = (
        "将数据生成为格式化的报告，支持输出为纯文本或网页格式"
    )
    examples = [
        {"input": {"title": "月度销售报告", "sections": [{"heading": "概览", "content": "本月销售额增长20%"}], "format": "markdown"}, "output_summary": "生成包含标题和章节的纯文本格式报告"},
        {"input": {"title": "客户分析", "sections": [{"heading": "客户分布", "table_data": [{"区域": "华东", "数量": 50}]}], "format": "html"}, "output_summary": "生成包含表格的网页格式报告"},
    ]
    related_tools = ["analyze_data"]
    gotchas = "标题和章节列表为必填项。章节中的表格数据必须是字典列表格式。"

    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "报告标题（必填）",
            },
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "heading": {"type": "string", "description": "章节标题"},
                        "content": {"type": "string", "description": "章节正文"},
                        "table_data": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "表格数据（可选），每行为一个字典",
                        },
                    },
                },
                "description": "报告章节列表（必填），每个章节包含 heading、content、table_data(可选)",
            },
            "format": {
                "type": "string",
                "description": "输出格式: markdown(默认) 或 html",
                "enum": ["markdown", "html"],
            },
        },
        "required": ["title", "sections"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        title = (args.get("title") or "").strip()
        sections = args.get("sections")
        fmt = args.get("format", "markdown")

        if not title:
            return "请提供报告标题（title 参数）。"
        if not sections or not isinstance(sections, list):
            return "请提供至少一个报告章节（sections 参数）。"

        # 构建 Markdown
        md_content = _build_markdown(title, sections)

        if fmt == "html":
            content = _md_to_simple_html(md_content)
        else:
            content = md_content

        result = {
            "format": fmt,
            "content": content,
            "char_count": len(content),
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
