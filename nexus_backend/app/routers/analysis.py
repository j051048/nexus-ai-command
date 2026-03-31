"""
智能数据分析路由
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import get_current_user_id, get_current_org_id
from app.core.responses import api_success, api_error
from app.tools.data_analysis_assistant import analyze_data_with_nl

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class AnalyzeRequest(BaseModel):
    query: str
    context: str = ""


@router.post("/query")
async def analyze_with_nl(
    request: AnalyzeRequest,
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    """自然语言数据分析"""
    try:
        result = await analyze_data_with_nl(
            query=request.query,
            org_id=org_id,
            context=request.context,
        )

        if not result.get("success"):
            return api_error(result.get("error", "分析失败"))

        return api_success(result)

    except Exception as e:
        logger.error(f"数据分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
