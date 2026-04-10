"""
招投标专业搜索工具

为 AI Agent 提供国内招投标数据查询能力，使用 APISpace 数据源。
当用户询问招标、投标、采购、政府招标等相关信息时，优先使用此工具。
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services import bidding_service
from app.tools._shared import safe_tool_error
from app.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

_CN_TZ = timezone(timedelta(hours=8))


class BiddingSearchTool(BaseTool):
    """搜索国内招投标项目信息"""

    name = "search_bidding_projects"
    domain = "tender"
    description = "搜索国内招投标和政府采购公告数据，支持按关键词和日期筛选"
    examples = [
        {
            "input": {"keyword": "人工智能"},
            "output_summary": "返回最近30天内与人工智能相关的招投标项目列表",
        },
        {
            "input": {
                "keyword": "服务器采购",
                "start_date": "2026-01-01",
                "end_date": "2026-03-01",
            },
            "output_summary": "返回指定日期范围内的服务器采购招标公告",
        },
    ]
    gotchas = "关键词为必填项。默认查询最近30天数据。招投标查询应使用此工具而非网页搜索。最多展示前10条结果。"
    related_tools = ["analyze_tender_document"]
    required_role = "all"

    @property
    def parameters(self) -> dict:
        """动态生成参数 schema，注入当前日期提示以避免 LLM 使用训练数据日期。"""
        today = datetime.now(_CN_TZ).strftime("%Y-%m-%d")
        thirty_days_ago = (datetime.now(_CN_TZ) - timedelta(days=30)).strftime(
            "%Y-%m-%d"
        )
        return {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词，如 '人工智能', '软件开发', '服务器采购'",
                },
                "start_date": {
                    "type": "string",
                    "description": (
                        f"发布起始日期 (yyyy-MM-dd)。"
                        f"当前日期是 {today}，不传则默认为 {thirty_days_ago}（30天前）。"
                        f"请根据用户意图和当前日期推算，勿使用训练数据中的日期。"
                    ),
                },
                "end_date": {
                    "type": "string",
                    "description": (
                        f"发布截止日期 (yyyy-MM-dd)。"
                        f"当前日期是 {today}，不传则默认为 {today}。"
                        f"请根据用户意图和当前日期推算，勿使用训练数据中的日期。"
                    ),
                },
            },
            "required": ["keyword"],
        }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        keyword = args.get("keyword", "").strip()
        if not keyword:
            return "请提供招投标搜索关键词。"

        start_date = args.get("start_date") or args.get("startDate")
        end_date = args.get("end_date") or args.get("endDate")

        # 后端兜底：LLM 未传日期时自动用当前时间计算
        now = datetime.now(_CN_TZ)
        if not end_date:
            end_date = now.strftime("%Y-%m-%d")
        if not start_date:
            start_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")

        logger.info(
            f"BiddingSearchTool: keyword={keyword}, date={start_date}~{end_date}"
        )

        try:
            result = await bidding_service.search_projects(
                keyword=keyword,
                start_date=start_date,
                end_date=end_date,
            )
        except ValueError as e:
            return safe_tool_error(e, "招投标查询配置")
        except Exception as e:
            logger.error(f"BiddingSearchTool error: {e}")
            return safe_tool_error(e, "招投标查询")

        if result.get("status") != "success":
            return f"招投标查询失败: {result.get('message', '未知错误')}"

        total = result.get("total", 0)
        projects = result.get("projects", [])

        if not projects:
            return f"未找到与「{keyword}」相关的招投标项目，可尝试调整关键词或扩大时间范围。"

        lines = [
            f"为您找到 **{total}** 条招投标记录（展示前 {min(len(projects), 10)} 条）：\n"
        ]

        for i, item in enumerate(projects[:10], 1):
            title = item.get("title", "未知标题")
            province = item.get("provinceName", "")
            pub_time = item.get("pubishTime", item.get("publishTime", ""))
            project_id = item.get("id", "")

            location = f"[{province}] " if province else ""
            time_str = f" | 发布: {pub_time[:10]}" if pub_time else ""
            lines.append(f"{i}. {location}**{title}**{time_str}")
            if project_id:
                lines.append(f"   项目ID: `{project_id}`")

        if total > 10:
            lines.append(f"\n共 {total} 条结果，如需查看更多请缩小搜索范围。")

        return "\n".join(lines)
