"""HR人力资源 API 路由"""

import logging
from fastapi import APIRouter, Depends, Request
from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/hr", tags=["HR"])


@router.get("/attendance")
async def list_attendance(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取HR考勤记录"""
    try:
        db = getattr(req.state, "db", None)
        org_id = getattr(req.state, "org_id", None)
        
        if not db:
            logger.error("Database connection not found in request state")
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        query = db.table("hr_attendance").select("*")
        # hr_attendance 表无 organization_id 列，通过 user_id 过滤
        query = query.eq("user_id", user_id)

        result = await query.execute()
        return api_success(data={"records": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list attendance: {str(e)}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取考勤数据失败")


@router.get("/salary")
async def list_salary(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取薪资记录"""
    try:
        db = getattr(req.state, "db", None)
        org_id = getattr(req.state, "org_id", None)
        
        if not db:
            logger.error("Database connection not found in request state")
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        # Basic query
        query = db.table("hr_salary_records").select("*")
        
        # Security: Salary records should ALWAYS be filtered by user_id for regular users
        # hr_salary_records 表无 organization_id 列
        query = query.eq("user_id", user_id)

        result = await query.execute()
        return api_success(data={"records": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list salary: {str(e)}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取薪资数据失败")


@router.get("/performance")
async def list_performance(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取绩效评审"""
    try:
        db = getattr(req.state, "db", None)
        org_id = getattr(req.state, "org_id", None)
        
        if not db:
            logger.error("Database connection not found in request state")
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        query = db.table("hr_performance_reviews").select("*")
        # hr_performance_reviews 表无 organization_id 列，通过 user_id 过滤
        query = query.eq("user_id", user_id)

        result = await query.execute()
        return api_success(data={"reviews": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list performance: {str(e)}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取绩效数据失败")


@router.get("/positions")
async def list_positions(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取职位列表"""
    try:
        db = getattr(req.state, "db", None)
        org_id = getattr(req.state, "org_id", None)
        
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        query = db.table("hr_job_positions").select("*")
        if org_id:
            query = query.eq("organization_id", org_id)

        result = await query.execute()
        return api_success(data={"positions": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list positions: {str(e)}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取职位信息失败")


@router.get("/candidates")
async def list_candidates(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取候选人列表"""
    try:
        db = getattr(req.state, "db", None)
        org_id = getattr(req.state, "org_id", None)
        
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        query = db.table("hr_candidates").select("*")
        if org_id:
            query = query.eq("organization_id", org_id)

        result = await query.execute()
        return api_success(data={"candidates": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list candidates: {str(e)}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取候选人信息失败")
