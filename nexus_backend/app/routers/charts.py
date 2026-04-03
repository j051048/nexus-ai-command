"""
图表生成路由
"""

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.responses import api_error, api_success
from app.tools.chart_generation_tool import generate_chart

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/charts", tags=["charts"])


class GenerateChartRequest(BaseModel):
    chart_type: Literal["line", "bar", "pie", "funnel", "scatter", "heatmap"]
    data: dict[str, Any]
    title: str = ""
    x_label: str = ""
    y_label: str = ""
    output_format: Literal["html", "json"] = "json"


@router.post("/generate")
async def create_chart(
    request: GenerateChartRequest,
    user_id: str = Depends(get_current_user_id),
):
    """生成图表"""
    try:
        result = await generate_chart(
            chart_type=request.chart_type,
            data=request.data,
            title=request.title,
            x_label=request.x_label,
            y_label=request.y_label,
            output_format=request.output_format,
        )

        if not result.get("success"):
            return api_error(result.get("error", "生成失败"))

        return api_success(result)

    except Exception as e:
        logger.error(f"图表生成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
