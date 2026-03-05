"""组织架构管理 API 路由 (部门/职位/员工)"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.organization_service import organization_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/org-structure", tags=["Organization Structure"])


# ── Schemas ──


class DepartmentCreate(BaseModel):
    name: str
    parent_id: str | None = None
    manager_id: str | None = None
    sort_order: int = 0


class DepartmentUpdate(BaseModel):
    name: str | None = None
    manager_id: str | None = None
    status: str | None = None


class EmployeeCreate(BaseModel):
    name: str
    department_id: str
    position_id: str | None = None
    phone: str | None = None
    email: str | None = None
    hire_date: str | None = None


class EmployeeUpdate(BaseModel):
    department_id: str | None = None
    position_id: str | None = None
    status: str | None = None
    phone: str | None = None
    email: str | None = None


class PositionCreate(BaseModel):
    name: str
    level: int = 1
    department_id: str | None = None


# ── Department Endpoints ──


@router.get("/departments")
async def list_departments(
    req: Request,
    parent_id: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """查询部门列表"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        departments = await organization_service.list_departments(
            org_id=org_id,
            parent_id=parent_id,
            db=db,
        )
        return api_success(data={"departments": departments})
    except Exception as e:
        logger.error(f"Failed to list departments: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/departments")
async def create_department(
    body: DepartmentCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建部门"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        department = await organization_service.create_department(
            org_id=org_id,
            name=body.name,
            parent_id=body.parent_id,
            manager_id=body.manager_id,
            sort_order=body.sort_order,
            db=db,
        )
        return api_success(data={"department": department}, message="部门创建成功")
    except Exception as e:
        logger.error(f"Failed to create department: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.patch("/departments/{department_id}")
async def update_department(
    department_id: str,
    body: DepartmentUpdate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新部门"""
    try:
        db = getattr(req.state, "db", None)
        updates = body.model_dump(exclude_none=True)
        if not updates:
            raise api_error(ErrorCode.VALIDATION_MISSING_FIELD, "请提供至少一个要更新的字段")
        department = await organization_service.update_department(
            department_id=department_id,
            updates=updates,
            db=db,
        )
        return api_success(data={"department": department}, message="部门更新成功")
    except Exception as e:
        logger.error(f"Failed to update department: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ── Position Endpoints ──


@router.get("/positions")
async def list_positions(
    req: Request,
    department_id: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """查询职位列表"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        positions = await organization_service.list_positions(
            org_id=org_id,
            department_id=department_id,
            db=db,
        )
        return api_success(data={"positions": positions})
    except Exception as e:
        logger.error(f"Failed to list positions: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/positions")
async def create_position(
    body: PositionCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建职位"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        position = await organization_service.create_position(
            org_id=org_id,
            name=body.name,
            level=body.level,
            department_id=body.department_id,
            db=db,
        )
        return api_success(data={"position": position}, message="职位创建成功")
    except Exception as e:
        logger.error(f"Failed to create position: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ── Employee Endpoints ──


@router.get("/employees")
async def list_employees(
    req: Request,
    department_id: str = None,
    status: str = None,
    search: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """查询员工列表"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        filters = {}
        if department_id:
            filters["department_id"] = department_id
        if status:
            filters["status"] = status
        if search:
            filters["search"] = search
        employees = await organization_service.list_employees(
            org_id=org_id,
            filters=filters if filters else None,
            db=db,
        )
        return api_success(data={"employees": employees})
    except Exception as e:
        logger.error(f"Failed to list employees: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/employees/{employee_id}")
async def get_employee_detail(
    employee_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取员工详情"""
    try:
        db = getattr(req.state, "db", None)
        employee = await organization_service.get_employee_detail(
            employee_id=employee_id,
            db=db,
        )
        if not employee:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "员工不存在")
        return api_success(data={"employee": employee})
    except Exception as e:
        logger.error(f"Failed to get employee detail: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/employees")
async def create_employee(
    body: EmployeeCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建员工"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        data = body.model_dump(exclude_none=True)
        employee = await organization_service.create_employee(
            org_id=org_id,
            data=data,
            db=db,
        )
        return api_success(data={"employee": employee}, message="员工创建成功")
    except Exception as e:
        logger.error(f"Failed to create employee: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.patch("/employees/{employee_id}")
async def update_employee(
    employee_id: str,
    body: EmployeeUpdate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新员工"""
    try:
        db = getattr(req.state, "db", None)
        updates = body.model_dump(exclude_none=True)
        if not updates:
            raise api_error(ErrorCode.VALIDATION_MISSING_FIELD, "请提供至少一个要更新的字段")
        employee = await organization_service.update_employee(
            employee_id=employee_id,
            updates=updates,
            db=db,
        )
        return api_success(data={"employee": employee}, message="员工更新成功")
    except Exception as e:
        logger.error(f"Failed to update employee: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ── Statistics ──


@router.get("/statistics")
async def org_statistics(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """组织统计"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        stats = await organization_service.get_org_statistics(org_id=org_id, db=db)
        return api_success(data=stats)
    except Exception as e:
        logger.error(f"Failed to get org statistics: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
