"""
数据可视化图表生成工具
支持销售漏斗、趋势图、饼图等常见图表类型
"""

import json
import logging
from typing import Any, Literal

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

ChartType = Literal["line", "bar", "pie", "funnel", "scatter", "heatmap"]


@tool
async def generate_chart(
    chart_type: ChartType,
    data: dict[str, Any],
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    output_format: Literal["html", "json"] = "json",
) -> dict[str, Any]:
    """生成数据可视化图表

    Args:
        chart_type: 图表类型 (line=折线图, bar=柱状图, pie=饼图, funnel=漏斗图, scatter=散点图, heatmap=热力图)
        data: 图表数据，格式根据图表类型而定
            - line/bar: {"x": ["Jan", "Feb"], "y": [100, 200]} 或 {"series": [{"name": "销售额", "data": [100, 200]}]}
            - pie: {"labels": ["A", "B"], "values": [30, 70]}
            - funnel: {"stages": ["线索", "商机", "成交"], "values": [1000, 500, 100]}
        title: 图表标题
        x_label: X轴标签
        y_label: Y轴标签
        output_format: 输出格式 (html=可嵌入网页, json=ECharts配置)

    Returns:
        包含图表配置或HTML的字典

    Examples:
        # 销售趋势折线图
        generate_chart(
            chart_type="line",
            data={"x": ["1月", "2月", "3月"], "y": [100, 150, 200]},
            title="月度销售趋势",
            y_label="销售额(万元)"
        )

        # 销售漏斗
        generate_chart(
            chart_type="funnel",
            data={"stages": ["线索", "商机", "报价", "成交"], "values": [1000, 500, 200, 50]},
            title="销售转化漏斗"
        )
    """
    try:
        # 构建 ECharts 配置
        option = _build_echarts_option(chart_type, data, title, x_label, y_label)

        if output_format == "html":
            html = _generate_html(option, title)
            return {"success": True, "format": "html", "content": html}
        else:
            return {"success": True, "format": "json", "option": option}

    except Exception as e:
        logger.error(f"生成图表失败: {e}")
        return {"success": False, "error": str(e)}


def _build_echarts_option(chart_type: ChartType, data: dict, title: str, x_label: str, y_label: str) -> dict:
    """构建 ECharts 配置"""
    base_option = {
        "title": {"text": title, "left": "center"},
        "tooltip": {"trigger": "axis" if chart_type in ["line", "bar"] else "item"},
        "legend": {"top": "bottom"},
    }

    if chart_type == "line":
        return {**base_option, **_build_line_chart(data, x_label, y_label)}
    elif chart_type == "bar":
        return {**base_option, **_build_bar_chart(data, x_label, y_label)}
    elif chart_type == "pie":
        return {**base_option, **_build_pie_chart(data)}
    elif chart_type == "funnel":
        return {**base_option, **_build_funnel_chart(data)}
    elif chart_type == "scatter":
        return {**base_option, **_build_scatter_chart(data, x_label, y_label)}
    elif chart_type == "heatmap":
        return {**base_option, **_build_heatmap_chart(data, x_label, y_label)}
    else:
        raise ValueError(f"不支持的图表类型: {chart_type}")


def _build_line_chart(data: dict, x_label: str, y_label: str) -> dict:
    """构建折线图"""
    if "series" in data:
        # 多系列数据
        return {
            "xAxis": {"type": "category", "data": data.get("x", []), "name": x_label},
            "yAxis": {"type": "value", "name": y_label},
            "series": [{"type": "line", "name": s["name"], "data": s["data"]} for s in data["series"]],
        }
    else:
        # 单系列数据
        return {
            "xAxis": {"type": "category", "data": data.get("x", []), "name": x_label},
            "yAxis": {"type": "value", "name": y_label},
            "series": [{"type": "line", "data": data.get("y", [])}],
        }


def _build_bar_chart(data: dict, x_label: str, y_label: str) -> dict:
    """构建柱状图"""
    if "series" in data:
        return {
            "xAxis": {"type": "category", "data": data.get("x", []), "name": x_label},
            "yAxis": {"type": "value", "name": y_label},
            "series": [{"type": "bar", "name": s["name"], "data": s["data"]} for s in data["series"]],
        }
    else:
        return {
            "xAxis": {"type": "category", "data": data.get("x", []), "name": x_label},
            "yAxis": {"type": "value", "name": y_label},
            "series": [{"type": "bar", "data": data.get("y", [])}],
        }


def _build_pie_chart(data: dict) -> dict:
    """构建饼图"""
    labels = data.get("labels", [])
    values = data.get("values", [])
    return {
        "series": [
            {
                "type": "pie",
                "radius": "50%",
                "data": [{"name": labels[i], "value": values[i]} for i in range(len(labels))],
            }
        ]
    }


def _build_funnel_chart(data: dict) -> dict:
    """构建漏斗图"""
    stages = data.get("stages", [])
    values = data.get("values", [])
    return {
        "series": [
            {
                "type": "funnel",
                "data": [{"name": stages[i], "value": values[i]} for i in range(len(stages))],
            }
        ]
    }


def _build_scatter_chart(data: dict, x_label: str, y_label: str) -> dict:
    """构建散点图"""
    return {
        "xAxis": {"name": x_label},
        "yAxis": {"name": y_label},
        "series": [{"type": "scatter", "data": data.get("points", [])}],
    }


def _build_heatmap_chart(data: dict, x_label: str, y_label: str) -> dict:
    """构建热力图"""
    return {
        "xAxis": {"type": "category", "data": data.get("x", []), "name": x_label},
        "yAxis": {"type": "category", "data": data.get("y", []), "name": y_label},
        "visualMap": {"min": 0, "max": data.get("max", 100), "calculable": True},
        "series": [{"type": "heatmap", "data": data.get("values", [])}],
    }


def _generate_html(option: dict, title: str) -> str:
    """生成可嵌入的HTML"""
    option_json = json.dumps(option, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
</head>
<body>
    <div id="chart" style="width: 100%; height: 600px;"></div>
    <script>
        var chart = echarts.init(document.getElementById('chart'));
        var option = {option_json};
        chart.setOption(option);
        window.addEventListener('resize', () => chart.resize());
    </script>
</body>
</html>"""
