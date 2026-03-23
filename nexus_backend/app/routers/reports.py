"""数据分析报表 API 端点"""

import logging

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.report_service import report_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["Reports"])


def _build_date_range(
    preset: str = None,
    start: str = None,
    end: str = None,
) -> dict:
    """从查询参数构建日期范围字典"""
    if preset:
        return {"preset": preset, "start": start, "end": end}
    if start or end:
        return {"preset": "custom", "start": start, "end": end}
    return {"preset": "month"}


@router.get("/sales")
async def get_sales_report(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    preset: str = Query(None, description="时间预设: today/week/month/quarter/custom"),
    start: str = Query(None, description="自定义开始日期 (ISO)"),
    end: str = Query(None, description="自定义结束日期 (ISO)"),
    group_by: str = Query("day", description="聚合维度: day/week/month"),
):
    """销售报表: 按日/周/月汇总销售额、成交数、转化率"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        date_range = _build_date_range(preset, start, end)
        data = await report_service.get_sales_report(org_id, date_range, group_by, db=db)
        return api_success(data=data)
    except Exception as e:
        logger.error(f"Sales report error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "报表操作失败")


@router.get("/approvals")
async def get_approval_report(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    preset: str = Query(None),
    start: str = Query(None),
    end: str = Query(None),
):
    """审批报表: 审批数量、平均处理时间、自动审批率、驳回率"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        date_range = _build_date_range(preset, start, end)
        data = await report_service.get_approval_report(org_id, date_range, db=db)
        return api_success(data=data)
    except Exception as e:
        logger.error(f"Approval report error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "报表操作失败")


@router.get("/performance")
async def get_performance_report(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    preset: str = Query(None),
    start: str = Query(None),
    end: str = Query(None),
):
    """绩效报表: 团队积分、个人排名、目标完成率"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        date_range = _build_date_range(preset, start, end)
        data = await report_service.get_performance_report(org_id, date_range, db=db)
        return api_success(data=data)
    except Exception as e:
        logger.error(f"Performance report error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "报表操作失败")


@router.get("/usage")
async def get_usage_report(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    preset: str = Query(None),
    start: str = Query(None),
    end: str = Query(None),
):
    """使用报表: AI 对话量、Token 消耗、功能使用频率"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        date_range = _build_date_range(preset, start, end)
        data = await report_service.get_usage_report(org_id, date_range, db=db)
        return api_success(data=data)
    except Exception as e:
        logger.error(f"Usage report error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "报表操作失败")


@router.get("/overview")
async def get_overview_stats(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """概览统计: 关键 KPI 汇总"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        data = await report_service.get_overview_stats(org_id, db=db)
        return api_success(data=data)
    except Exception as e:
        logger.error(f"Overview stats error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "报表操作失败")
