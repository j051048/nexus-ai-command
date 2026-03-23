"""
DataAnalysis 工具 — 对提供的数据集进行统计分析。

纯 Python 实现，不依赖 pandas，使用 statistics 标准库。
"""

import json
import logging
import statistics
from datetime import datetime
from typing import Any

from .base_tool import BaseTool
from app.tools._shared import safe_tool_error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 时间字段自动检测
# ---------------------------------------------------------------------------
_TIME_FIELD_NAMES = {"date", "time", "created_at", "updated_at", "timestamp", "日期", "时间"}


def _detect_time_field(records: list[dict]) -> str | None:
    """自动检测数据中的时间字段名。"""
    if not records:
        return None
    first = records[0]
    # 优先匹配常见名称
    for key in first:
        if key.lower() in _TIME_FIELD_NAMES:
            return key
    # 尝试解析值
    for key, val in first.items():
        if isinstance(val, str):
            try:
                datetime.fromisoformat(val.replace("Z", "+00:00"))
                return key
            except (ValueError, TypeError):
                continue
    return None


def _extract_numeric(records: list[dict], field: str) -> list[float]:
    """从记录中提取指定字段的数值列表，跳过无效值。"""
    values = []
    for r in records:
        v = r.get(field)
        if v is None:
            continue
        try:
            values.append(float(v))
        except (TypeError, ValueError):
            continue
    return values


def _find_numeric_fields(records: list[dict]) -> list[str]:
    """自动发现所有数值型字段。"""
    if not records:
        return []
    candidates = []
    sample = records[0]
    for key, val in sample.items():
        if isinstance(val, (int, float)):
            candidates.append(key)
        elif isinstance(val, str):
            try:
                float(val)
                candidates.append(key)
            except (TypeError, ValueError):
                continue
    return candidates


# ---------------------------------------------------------------------------
# 分析函数
# ---------------------------------------------------------------------------


def _summary(records: list[dict], value_field: str | None) -> dict:
    """汇总统计。"""
    result: dict[str, Any] = {"record_count": len(records)}
    numeric_fields = [value_field] if value_field else _find_numeric_fields(records)

    field_stats = {}
    for field in numeric_fields:
        nums = _extract_numeric(records, field)
        if not nums:
            continue
        field_stats[field] = {
            "count": len(nums),
            "min": round(min(nums), 2),
            "max": round(max(nums), 2),
            "sum": round(sum(nums), 2),
            "avg": round(statistics.mean(nums), 2),
            "median": round(statistics.median(nums), 2),
        }
    result["field_statistics"] = field_stats
    return result


def _group_by(records: list[dict], group_field: str, value_field: str | None) -> dict:
    """按字段分组统计。"""
    groups: dict[str, list[dict]] = {}
    for r in records:
        key = str(r.get(group_field, "(空)"))
        groups.setdefault(key, []).append(r)

    result_groups = []
    for key, items in groups.items():
        entry: dict[str, Any] = {"group": key, "count": len(items)}
        if value_field:
            nums = _extract_numeric(items, value_field)
            if nums:
                entry["sum"] = round(sum(nums), 2)
                entry["avg"] = round(statistics.mean(nums), 2)
        result_groups.append(entry)

    result_groups.sort(key=lambda x: x["count"], reverse=True)
    return {"group_field": group_field, "groups": result_groups}


def _trend(records: list[dict], value_field: str | None) -> dict:
    """时序趋势分析。"""
    time_field = _detect_time_field(records)
    if not time_field:
        return {"error": "未检测到时间字段，无法进行趋势分析。"}

    # 排序
    def _parse_time(r):
        v = r.get(time_field, "")
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return datetime.min

    sorted_records = sorted(records, key=_parse_time)

    # 按日聚合
    daily: dict[str, list[float]] = {}
    for r in sorted_records:
        v = str(r.get(time_field, ""))[:10]  # YYYY-MM-DD
        if value_field:
            try:
                daily.setdefault(v, []).append(float(r.get(value_field, 0)))
            except (TypeError, ValueError):
                daily.setdefault(v, []).append(0)
        else:
            daily.setdefault(v, []).append(1)

    trend_data = []
    for date_str, vals in daily.items():
        trend_data.append({
            "date": date_str,
            "count": len(vals),
            "sum": round(sum(vals), 2),
        })

    return {"time_field": time_field, "trend": trend_data}


def _top_n(records: list[dict], value_field: str, n: int) -> dict:
    """返回 Top N 记录。"""
    if not value_field:
        return {"error": "top_n 分析需要指定 value_field 参数。"}

    scored = []
    for r in records:
        try:
            score = float(r.get(value_field, 0))
        except (TypeError, ValueError):
            score = 0
        scored.append((score, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [item[1] for item in scored[:n]]
    return {"value_field": value_field, "n": n, "results": top}


# ---------------------------------------------------------------------------
# 工具类
# ---------------------------------------------------------------------------
class DataAnalysisTool(BaseTool):
    """对提供的数据集进行统计分析。"""

    name = "analyze_data"
    description = (
        "对数据集执行统计分析，支持汇总、分组聚合、时序趋势和排名"
    )
    domain = "analytics"
    examples = [
        {"input": {"data": [{"name": "A", "amount": 100}, {"name": "B", "amount": 200}], "analysis_type": "summary"}, "output_summary": "返回记录数、最小值、最大值、平均值、中位数等汇总统计"},
        {"input": {"data": [{"region": "华东", "sales": 500}], "analysis_type": "group_by", "group_field": "region", "value_field": "sales"}, "output_summary": "按区域分组统计销售额的合计和平均值"},
        {"input": {"data": [{"date": "2026-01-01", "revenue": 1000}], "analysis_type": "top_n", "value_field": "revenue", "n": 5}, "output_summary": "返回收入最高的前5条记录"},
    ]
    related_tools = ["generate_report"]
    gotchas = "数据必须是字典列表格式。分组分析必须指定分组字段。趋势分析需要数据中包含时间字段。排名分析必须指定数值字段。"

    parameters = {
        "type": "object",
        "properties": {
            "data": {
                "type": "array",
                "items": {"type": "object"},
                "description": "数据记录列表，每条记录是一个字典（必填）",
            },
            "analysis_type": {
                "type": "string",
                "description": "分析类型: summary(汇总统计) | group_by(分组聚合) | trend(时序趋势) | top_n(排名)",
                "enum": ["summary", "group_by", "trend", "top_n"],
            },
            "group_field": {
                "type": "string",
                "description": "分组字段名（group_by 时必填）",
            },
            "value_field": {
                "type": "string",
                "description": "数值字段名，用于统计计算",
            },
            "n": {
                "type": "integer",
                "description": "Top N 数量，默认 10",
            },
        },
        "required": ["data"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        data = args.get("data")
        if not data or not isinstance(data, list):
            return "请提供有效的数据列表（data 参数）。"
        if not all(isinstance(r, dict) for r in data):
            return "data 中的每条记录必须是字典格式。"

        analysis_type = args.get("analysis_type", "summary")
        group_field = args.get("group_field")
        value_field = args.get("value_field")
        n = args.get("n", 10)
        try:
            n = max(1, min(int(n), 100))
        except (TypeError, ValueError):
            n = 10

        handlers = {
            "summary": lambda: _summary(data, value_field),
            "group_by": lambda: _group_by(data, group_field, value_field)
            if group_field
            else {"error": "group_by 分析需要指定 group_field 参数。"},
            "trend": lambda: _trend(data, value_field),
            "top_n": lambda: _top_n(data, value_field, n),
        }

        handler = handlers.get(analysis_type)
        if not handler:
            return f"不支持的分析类型: {analysis_type}，可选: summary, group_by, trend, top_n"

        try:
            result = handler()
        except Exception as e:
            logger.exception("数据分析失败")
            return safe_tool_error(e, "数据分析")

        return json.dumps(
            {"analysis_type": analysis_type, "result": result},
            ensure_ascii=False,
            indent=2,
            default=str,
        )
