"""
招投标专业搜索工具

为 AI Agent 提供国内招投标数据查询能力，使用 APISpace 数据源。
当用户询问招标、投标、采购、政府招标等相关信息时，优先使用此工具。
"""

import logging
from typing import Any

from app.services import bidding_service
from app.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class BiddingSearchTool(BaseTool):
    """搜索国内招投标项目信息"""

    name = "search_bidding_projects"
    description = (
        "搜索国内最新的招投标、政府采购、企业招标公告数据。"
        "当用户询问招标信息、投标机会、采购公告、商机、政府招标项目时必须调用此工具。"
        "不要用 web_search 搜索招投标相关信息，应当使用本工具查询专业的招投标数据库。"
        "支持按关键词、日期范围筛选。默认查询最近30天的数据。"
    )
    required_role = "all"

    parameters = {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "搜索关键词，如 '人工智能', '软件开发', '服务器采购'",
            },
            "start_date": {
                "type": "string",
                "description": "发布起始日期 (yyyy-MM-dd)，默认30天前",
            },
            "end_date": {
                "type": "string",
                "description": "发布截止日期 (yyyy-MM-dd)，默认今天",
            },
        },
        "required": ["keyword"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        keyword = args.get("keyword", "").strip()
        if not keyword:
            return "请提供招投标搜索关键词。"

        start_date = args.get("start_date") or args.get("startDate")
        end_date = args.get("end_date") or args.get("endDate")

        logger.info(f"BiddingSearchTool: keyword={keyword}, date={start_date}~{end_date}")

        try:
            result = await bidding_service.search_projects(
                keyword=keyword,
                start_date=start_date,
                end_date=end_date,
            )
        except ValueError as e:
            return f"招投标查询配置错误: {e}"
        except Exception as e:
            logger.error(f"BiddingSearchTool error: {e}")
            return f"招投标查询系统错误: {e}"

        if result.get("status") != "success":
            return f"招投标查询失败: {result.get('message', '未知错误')}"

        total = result.get("total", 0)
        projects = result.get("projects", [])

        if not projects:
            return f"未找到与「{keyword}」相关的招投标项目，可尝试调整关键词或扩大时间范围。"

        lines = [f"为您找到 **{total}** 条招投标记录（展示前 {min(len(projects), 10)} 条）：\n"]

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
