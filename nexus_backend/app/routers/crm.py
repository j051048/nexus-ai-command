"""CRM 客户关系管理 API 端点"""

import logging
from fastapi import APIRouter, Request, Depends, Query
from app.core.auth import get_current_user_id
from app.core.errors import api_success, api_error, api_list, ErrorCode
from app.services.crm_service import crm_service, CUSTOMER_STAGES, ACTIVITY_TYPES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crm", tags=["CRM"])


@router.get("/customers")
async def list_customers(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    stage: str = Query(None, description="按阶段筛选"),
    industry: str = Query(None, description="按行业筛选"),
    search: str = Query(None, description="搜索关键词"),
):
    """获取客户列表（支持筛选和搜索）"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)

        if search:
            customers = await crm_service.search_customers(org_id, search, db=db)
        else:
            filters = {}
            if stage:
                filters["stage"] = stage
            if industry:
                filters["industry"] = industry
            customers = await crm_service.list_customers(org_id, filters, db=db)

        return api_list(items=customers, total=len(customers))
    except Exception as e:
        logger.error(f"List customers error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/customers")
async def create_customer(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建新客户"""
    try:
        body = await req.json()
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        customer = await crm_service.create_customer(org_id, body, db=db)
        return api_success(data={"customer": customer}, message="客户创建成功")
    except ValueError as e:
        return api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
    except Exception as e:
        logger.error(f"Create customer error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/customers/{customer_id}")
async def get_customer(
    customer_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取客户详情"""
    try:
        db = getattr(req.state, "db", None)
        customer = await crm_service.get_customer(customer_id, db=db)
        if not customer:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "客户不存在")
        return api_success(data={"customer": customer})
    except Exception as e:
        logger.error(f"Get customer error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/customers/{customer_id}")
async def update_customer(
    customer_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新客户信息"""
    try:
        body = await req.json()
        db = getattr(req.state, "db", None)
        customer = await crm_service.update_customer(customer_id, body, db=db)
        return api_success(data={"customer": customer}, message="客户信息已更新")
    except ValueError as e:
        return api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
    except Exception as e:
        logger.error(f"Update customer error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/customers/{customer_id}/contacts")
async def list_contacts(
    customer_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取客户联系人列表"""
    try:
        db = getattr(req.state, "db", None)
        contacts = await crm_service.list_contacts(customer_id, db=db)
        return api_list(items=contacts, total=len(contacts))
    except Exception as e:
        logger.error(f"List contacts error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/customers/{customer_id}/contacts")
async def create_contact(
    customer_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """添加联系人"""
    try:
        body = await req.json()
        db = getattr(req.state, "db", None)
        contact = await crm_service.create_contact(customer_id, body, db=db)
        return api_success(data={"contact": contact}, message="联系人已添加")
    except ValueError as e:
        return api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
    except Exception as e:
        logger.error(f"Create contact error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/customers/{customer_id}/timeline")
async def get_timeline(
    customer_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(20, ge=1, le=100),
):
    """获取客户活动时间线"""
    try:
        db = getattr(req.state, "db", None)
        activities = await crm_service.get_activity_timeline(customer_id, limit, db=db)
        return api_list(items=activities, total=len(activities))
    except Exception as e:
        logger.error(f"Get timeline error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/customers/{customer_id}/activities")
async def create_activity(
    customer_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """添加活动记录"""
    try:
        body = await req.json()
        activity_type = body.get("activity_type")
        content = body.get("content", "")

        if not activity_type:
            return api_error(ErrorCode.VALIDATION_MISSING_FIELD, "activity_type 为必填字段")

        db = getattr(req.state, "db", None)
        activity = await crm_service.create_activity(
            customer_id, activity_type, content, user_id, db=db
        )
        return api_success(data={"activity": activity}, message="活动记录已添加")
    except ValueError as e:
        return api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
    except Exception as e:
        logger.error(f"Create activity error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/stats")
async def get_customer_stats(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取客户统计数据"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        stats = await crm_service.get_customer_stats(org_id, db=db)
        return api_success(data={"stats": stats})
    except Exception as e:
        logger.error(f"Customer stats error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/stages")
async def get_stages():
    """获取客户阶段定义"""
    return api_success(data={"stages": CUSTOMER_STAGES})


@router.get("/activity-types")
async def get_activity_types():
    """获取活动类型定义"""
    return api_success(data={"activity_types": ACTIVITY_TYPES})
