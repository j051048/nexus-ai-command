"""AI 培训助手 API 路由"""

import logging

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.training_service import training_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/training", tags=["Training"])


@router.get("/courses")
async def list_courses(
    user_id: str = Depends(get_current_user_id),
):
    """获取所有培训课程"""
    try:
        courses = await training_service.list_courses()
        return api_success(data={"courses": courses})
    except Exception as e:
        logger.error(f"Failed to list courses: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "培训操作失败")


@router.get("/courses/{course_id}")
async def get_course(
    course_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """获取课程详情"""
    course = await training_service.get_course(course_id)
    if not course:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "课程不存在")
    return api_success(data={"course": course})


@router.get("/progress")
async def get_progress(
    req: Request,
    course_id: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """获取学习进度"""
    try:
        db = getattr(req.state, "db", None)
        progress = await training_service.get_user_progress(
            user_id=user_id, course_id=course_id, db=db
        )
        return api_success(data={"progress": progress})
    except Exception as e:
        logger.error(f"Failed to get progress: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "培训操作失败")


@router.post("/progress")
async def update_progress(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新学习进度"""
    try:
        body = await req.json()
        db = getattr(req.state, "db", None)
        result = await training_service.update_progress(
            user_id=user_id,
            course_id=body.get("course_id"),
            module_id=body.get("module_id"),
            completed=body.get("completed", True),
            score=body.get("score"),
            db=db,
        )
        return api_success(data={"progress": result}, message="进度已更新")
    except ValueError:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "培训参数校验失败")
    except Exception as e:
        logger.error(f"Failed to update progress: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "培训操作失败")


@router.post("/quiz/submit")
async def submit_quiz(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """提交测验答案"""
    try:
        body = await req.json()
        db = getattr(req.state, "db", None)
        result = await training_service.submit_quiz(
            user_id=user_id,
            course_id=body.get("course_id"),
            module_id=body.get("module_id"),
            answers=body.get("answers", {}),
            db=db,
        )
        return api_success(data={"quiz_result": result})
    except ValueError:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "培训参数校验失败")
    except Exception as e:
        logger.error(f"Failed to submit quiz: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "培训操作失败")
