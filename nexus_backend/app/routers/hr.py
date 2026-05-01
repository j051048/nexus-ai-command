"""HR人力资源 API 路由"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/hr", tags=["HR"])


# ─── Pydantic 请求模型 ────────────────────────────────────────


class EmployeeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="员工姓名")
    email: str | None = Field(None, max_length=200, description="邮箱")
    phone: str | None = Field(None, max_length=50, description="手机号")
    department: str | None = Field(None, max_length=100, description="部门")
    position: str | None = Field(None, max_length=100, description="职位")
    hire_date: str | None = Field(None, description="入职日期")
    salary: float | None = Field(None, ge=0, description="薪资")


class EmployeeUpdate(BaseModel):
    name: str | None = Field(None, max_length=100, description="员工姓名")
    email: str | None = Field(None, max_length=200, description="邮箱")
    phone: str | None = Field(None, max_length=50, description="手机号")
    department: str | None = Field(None, max_length=100, description="部门")
    position: str | None = Field(None, max_length=100, description="职位")
    salary: float | None = Field(None, ge=0, description="薪资")
    status: str | None = Field(None, max_length=50, description="状态")


class PerformanceUpdate(BaseModel):
    score: float | None = Field(None, ge=0, le=100, description="绩效分数")
    review_period: str | None = Field(None, max_length=50, description="考核周期")
    reviewer: str | None = Field(None, max_length=100, description="考核人")
    comments: str | None = Field(None, max_length=2000, description="评语")
    status: str | None = Field(None, max_length=50, description="状态")


class CandidateStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1, max_length=50, description="候选人状态")
    notes: str | None = Field(None, max_length=1000, description="备注")


@router.get("/attendance")
async def list_attendance(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取HR考勤记录"""
    try:
        db = getattr(req.state, "db", None)
        getattr(req.state, "org_id", None)

        if not db:
            logger.error("Database connection not found in request state")
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        query = db.table("hr_attendance").select("*")
        # hr_attendance 表无 organization_id 列，通过 user_id 过滤
        query = query.eq("user_id", user_id)

        result = await query.limit(500).execute()
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
        getattr(req.state, "org_id", None)

        if not db:
            logger.error("Database connection not found in request state")
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        # Basic query
        query = db.table("hr_salary_records").select("*")

        # Security: Salary records should ALWAYS be filtered by user_id for regular users
        # hr_salary_records 表无 organization_id 列
        query = query.eq("user_id", user_id)

        result = await query.limit(500).execute()
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
        getattr(req.state, "org_id", None)

        if not db:
            logger.error("Database connection not found in request state")
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        query = db.table("hr_performance_reviews").select("*")
        # hr_performance_reviews 表无 organization_id 列，通过 user_id 过滤
        query = query.eq("user_id", user_id)

        result = await query.limit(500).execute()
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

        result = await query.limit(200).execute()
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

        result = await query.limit(200).execute()
        return api_success(data={"candidates": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list candidates: {str(e)}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取候选人信息失败")


# ─── 写操作端点 ────────────────────────────────────────────────


@router.post("/employees")
async def create_employee(
    req: Request,
    body: EmployeeCreate,
    user_id: str = Depends(get_current_user_id),
):
    """创建员工"""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

    db = getattr(req.state, "db", None)
    if not db:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

    try:
        insert_data = {
            "name": body.name,
            "organization_id": org_id,
            "created_by": user_id,
        }
        # 仅填充非空可选字段
        if body.email is not None:
            insert_data["email"] = body.email
        if body.phone is not None:
            insert_data["phone"] = body.phone
        if body.department is not None:
            insert_data["department"] = body.department
        if body.position is not None:
            insert_data["position"] = body.position
        if body.hire_date is not None:
            insert_data["hire_date"] = body.hire_date
        if body.salary is not None:
            insert_data["salary"] = body.salary

        result = await db.table("hr_employees").insert(insert_data).execute()

        if not result.data:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "创建员工失败")

        return api_success(data=result.data[0], message="员工创建成功")
    except Exception as e:
        if hasattr(e, "status_code") and e.status_code:
            raise
        logger.error(f"Failed to create employee: {str(e)}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "创建员工失败")


@router.put("/employees/{employee_id}")
async def update_employee(
    req: Request,
    employee_id: str,
    body: EmployeeUpdate,
    user_id: str = Depends(get_current_user_id),
):
    """更新员工信息"""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

    db = getattr(req.state, "db", None)
    if not db:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

    try:
        # 构建更新数据，仅包含非空字段
        update_data = {
            "updated_by": user_id,
            "updated_at": datetime.utcnow().isoformat(),
        }
        if body.name is not None:
            update_data["name"] = body.name
        if body.email is not None:
            update_data["email"] = body.email
        if body.phone is not None:
            update_data["phone"] = body.phone
        if body.department is not None:
            update_data["department"] = body.department
        if body.position is not None:
            update_data["position"] = body.position
        if body.salary is not None:
            update_data["salary"] = body.salary
        if body.status is not None:
            update_data["status"] = body.status

        result = await (
            db.table("hr_employees")
            .update(update_data)
            .eq("id", employee_id)
            .eq("organization_id", org_id)
            .execute()
        )

        if not result.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "员工不存在或无权限修改")

        return api_success(data=result.data[0], message="员工信息更新成功")
    except Exception as e:
        if hasattr(e, "status_code") and e.status_code:
            raise
        logger.error(f"Failed to update employee: {str(e)}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "更新员工信息失败")


@router.put("/performance/{review_id}")
async def update_performance(
    req: Request,
    review_id: str,
    body: PerformanceUpdate,
    user_id: str = Depends(get_current_user_id),
):
    """更新绩效评估"""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

    db = getattr(req.state, "db", None)
    if not db:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

    try:
        update_data = {"updated_by": user_id}
        if body.score is not None:
            update_data["score"] = body.score
        if body.review_period is not None:
            update_data["review_period"] = body.review_period
        if body.reviewer is not None:
            update_data["reviewer"] = body.reviewer
        if body.comments is not None:
            update_data["comments"] = body.comments
        if body.status is not None:
            update_data["status"] = body.status

        result = await (
            db.table("hr_performance_reviews")
            .update(update_data)
            .eq("id", review_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not result.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "绩效评估不存在或无权限修改")

        return api_success(data=result.data[0], message="绩效评估更新成功")
    except Exception as e:
        if hasattr(e, "status_code") and e.status_code:
            raise
        logger.error(f"Failed to update performance: {str(e)}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "更新绩效评估失败")


@router.put("/candidates/{candidate_id}/status")
async def update_candidate_status(
    req: Request,
    candidate_id: str,
    body: CandidateStatusUpdate,
    user_id: str = Depends(get_current_user_id),
):
    """更新候选人状态"""
    org_id = getattr(req.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

    db = getattr(req.state, "db", None)
    if not db:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

    try:
        update_data: dict = {
            "status": body.status,
            "updated_by": user_id,
        }
        if body.notes is not None:
            update_data["notes"] = body.notes

        result = await (
            db.table("hr_candidates")
            .update(update_data)
            .eq("id", candidate_id)
            .eq("organization_id", org_id)
            .execute()
        )

        if not result.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "候选人不存在或无权限修改")

        return api_success(data=result.data[0], message="候选人状态更新成功")
    except Exception as e:
        if hasattr(e, "status_code") and e.status_code:
            raise
        logger.error(f"Failed to update candidate status: {str(e)}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "更新候选人状态失败")
