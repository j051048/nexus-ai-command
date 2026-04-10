"""CRM 客户关系管理 API 端点"""

import logging

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, field_validator

from app.core.auth import get_current_user_id
from app.core.dependencies import require_role
from app.core.errors import ErrorCode, api_error, api_list, api_success
from app.services.crm_service import ACTIVITY_TYPES, CUSTOMER_STAGES, crm_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crm", tags=["CRM"])


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------


class CreateCustomerRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="客户名称")
    company: str | None = Field(None, max_length=200)
    industry: str | None = Field(None, max_length=100)
    stage: str | None = Field("lead")
    source: str | None = Field(None, max_length=100)
    estimated_value: float | None = Field(None, ge=0)
    tags: list[str] | None = None
    metadata: dict | None = None

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, v: str | None) -> str | None:
        valid = {"lead", "prospect", "opportunity", "customer", "churned"}
        if v and v not in valid:
            raise ValueError(f"stage must be one of {valid}")
        return v


class UpdateCustomerRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    company: str | None = Field(None, max_length=200)
    industry: str | None = Field(None, max_length=100)
    stage: str | None = None
    source: str | None = Field(None, max_length=100)
    estimated_value: float | None = Field(None, ge=0)
    assigned_to: str | None = None
    tags: list[str] | None = None
    metadata: dict | None = None

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, v: str | None) -> str | None:
        valid = {"lead", "prospect", "opportunity", "customer", "churned"}
        if v and v not in valid:
            raise ValueError(f"stage must be one of {valid}")
        return v


class CreateContactRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    title: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=200)
    is_primary: bool | None = False


class CreateActivityRequest(BaseModel):
    activity_type: str = Field(..., min_length=1, max_length=50)
    content: str = Field("", max_length=5000)

    @field_validator("activity_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        valid = set(ACTIVITY_TYPES.keys())
        if v not in valid:
            raise ValueError(f"activity_type must be one of {valid}")
        return v


class UpdateContactRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    title: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=200)
    is_primary: bool | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/customers")
async def list_customers(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    stage: str = Query(None, description="按阶段筛选"),
    industry: str = Query(None, description="按行业筛选"),
    search: str = Query(None, description="搜索关键词"),
    offset: int = Query(0, ge=0, description="分页偏移量"),
    limit: int = Query(50, ge=1, le=200, description="每页数量"),
):
    """获取客户列表（支持筛选、搜索和分页）"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
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

        total = len(customers)
        paginated = customers[offset : offset + limit]
        return api_list(items=paginated, total=total)
    except Exception as e:
        logger.error(f"List customers error: user={user_id} org={getattr(req.state, 'org_id', None)} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "CRM操作失败")


@router.post("/customers")
async def create_customer(
    body: CreateCustomerRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建新客户"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        customer = await crm_service.create_customer(org_id, body.model_dump(exclude_none=True), db=db)
        return api_success(data={"customer": customer}, message="客户创建成功")
    except ValueError:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "CRM参数校验失败")
    except Exception as e:
        logger.error(f"Create customer error: user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "CRM操作失败")


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
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "客户不存在")
        return api_success(data={"customer": customer})
    except Exception as e:
        logger.error(f"Get customer error: id={customer_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "CRM操作失败")


@router.put("/customers/{customer_id}")
async def update_customer(
    customer_id: str,
    body: UpdateCustomerRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新客户信息"""
    try:
        db = getattr(req.state, "db", None)
        customer = await crm_service.update_customer(customer_id, body.model_dump(exclude_none=True), db=db)
        return api_success(data={"customer": customer}, message="客户信息已更新")
    except ValueError:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "CRM参数校验失败")
    except Exception as e:
        logger.error(f"Update customer error: id={customer_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "CRM操作失败")


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
        logger.error(f"List contacts error: customer={customer_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "CRM操作失败")


@router.post("/customers/{customer_id}/contacts")
async def create_contact(
    customer_id: str,
    body: CreateContactRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """添加联系人"""
    try:
        db = getattr(req.state, "db", None)
        contact = await crm_service.create_contact(customer_id, body.model_dump(), db=db)
        return api_success(data={"contact": contact}, message="联系人已添加")
    except ValueError:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "CRM参数校验失败")
    except Exception as e:
        logger.error(f"Create contact error: customer={customer_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "CRM操作失败")


@router.put("/customers/{customer_id}/contacts/{contact_id}")
async def update_contact(
    customer_id: str,
    contact_id: str,
    body: UpdateContactRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新联系人信息"""
    try:
        db = getattr(req.state, "db", None)
        contact = await crm_service.update_contact(contact_id, body.model_dump(exclude_none=True), db=db)
        return api_success(data={"contact": contact}, message="联系人已更新")
    except ValueError:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "CRM参数校验失败")
    except Exception as e:
        logger.error(f"Update contact error: contact={contact_id} customer={customer_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "CRM操作失败")


@router.delete("/customers/{customer_id}/contacts/{contact_id}")
async def delete_contact(
    customer_id: str,
    contact_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """删除联系人"""
    try:
        db = getattr(req.state, "db", None)
        await crm_service.delete_contact(contact_id, db=db)
        return api_success(data=None, message="联系人已删除")
    except Exception as e:
        logger.error(f"Delete contact error: contact={contact_id} customer={customer_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "CRM操作失败")


@router.delete("/customers/{customer_id}")
async def delete_customer(
    customer_id: str,
    req: Request,
    user_id: str = Depends(require_role(["boss", "manager"])),
):
    """删除客户（仅 boss/manager，级联删除联系人和活动记录）"""
    try:
        db = getattr(req.state, "db", None)
        await crm_service.delete_customer(customer_id, db=db)
        return api_success(data=None, message="客户已删除")
    except Exception as e:
        logger.error(f"Delete customer error: id={customer_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "CRM操作失败")


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
        logger.error(f"Get timeline error: customer={customer_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "CRM操作失败")


@router.post("/customers/{customer_id}/activities")
async def create_activity(
    customer_id: str,
    body: CreateActivityRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """添加活动记录"""
    try:
        db = getattr(req.state, "db", None)
        activity = await crm_service.create_activity(customer_id, body.activity_type, body.content, user_id, db=db)
        return api_success(data={"activity": activity}, message="活动记录已添加")
    except ValueError:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "CRM参数校验失败")
    except Exception as e:
        logger.error(f"Create activity error: customer={customer_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "CRM操作失败")


@router.get("/stats")
async def get_customer_stats(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取客户统计数据"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        stats = await crm_service.get_customer_stats(org_id, db=db)
        return api_success(data={"stats": stats})
    except Exception as e:
        logger.error(f"Customer stats error: user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "CRM操作失败")


@router.get("/stages")
async def get_stages():
    """获取客户阶段定义"""
    return api_success(data={"stages": CUSTOMER_STAGES})


@router.get("/activity-types")
async def get_activity_types():
    """获取活动类型定义"""
    return api_success(data={"activity_types": ACTIVITY_TYPES})


@router.get("/customers/{customer_id}/health")
async def get_customer_health(
    customer_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取客户健康度评分与流失风险"""
    try:
        db = getattr(req.state, "db", None) or _get_db()
        org_id = getattr(req.state, "org_id", None)
        if not db or not org_id:
            return api_success(data={"health_score": 0, "risk_level": "unknown"})

        from datetime import datetime, timedelta

        now = datetime.utcnow()
        tenant_id = str(org_id)

        # 1. Fetch customer
        cust_res = await db.table("customers").select("*").eq("id", customer_id).eq("organization_id", tenant_id).execute()
        if not cust_res.data:
            return api_success(data={"health_score": 0, "risk_level": "unknown"})
        cust = cust_res.data[0]

        # 2. Activity recency (0-30): days since last activity
        act_res = await db.table("customer_activities").select("created_at").eq("customer_id", customer_id).order("created_at", desc=True).limit(1).execute()
        if act_res.data:
            last_act = datetime.fromisoformat(act_res.data[0]["created_at"].replace("Z", "+00:00")).replace(tzinfo=None)
            days_since = (now - last_act).days
            activity_score = max(0, 30 - days_since)  # 30 if today, 0 if 30+ days
        else:
            activity_score = 0

        # 3. Activity frequency (0-20): count of activities in last 30 days
        month_ago = (now - timedelta(days=30)).isoformat()
        freq_res = await db.table("customer_activities").select("id", count="exact").eq("customer_id", customer_id).gte("created_at", month_ago).execute()
        freq_count = freq_res.count or 0
        frequency_score = min(20, freq_count * 2)  # 2 pts per activity, max 20

        # 4. Contact richness (0-15): number of contacts
        contact_res = await db.table("customer_contacts").select("id", count="exact").eq("customer_id", customer_id).execute()
        contact_count = contact_res.count or 0
        contact_score = min(15, contact_count * 5)  # 5 pts per contact, max 15

        # 5. Stage progression (0-20): based on customer stage
        stage_scores = {"lead": 5, "prospect": 10, "opportunity": 15, "customer": 20, "churned": 0}
        stage_score = stage_scores.get(cust.get("stage", ""), 5)

        # 6. Value indicator (0-15): estimated value
        ev = float(cust.get("estimated_value", 0) or 0)
        if ev >= 100000:
            value_score = 15
        elif ev >= 50000:
            value_score = 10
        elif ev >= 10000:
            value_score = 5
        else:
            value_score = 2

        health_score = activity_score + frequency_score + contact_score + stage_score + value_score

        # Risk classification
        if health_score >= 70:
            risk_level = "healthy"
        elif health_score >= 40:
            risk_level = "at_risk"
        else:
            risk_level = "churn_risk"

        return api_success(data={
            "customer_id": customer_id,
            "health_score": health_score,
            "risk_level": risk_level,
            "breakdown": {
                "activity_recency": activity_score,
                "activity_frequency": frequency_score,
                "contact_richness": contact_score,
                "stage_progression": stage_score,
                "value_indicator": value_score,
            },
            "days_since_last_activity": days_since if act_res.data else None,
            "activities_last_30d": freq_count,
            "contact_count": contact_count,
            "stage": cust.get("stage"),
            "estimated_value": ev,
        })
    except Exception as e:
        logger.error(f"Customer health error: id={customer_id} err={e}")
        return api_success(data={"health_score": 0, "risk_level": "unknown"})


@router.get("/health-overview")
async def get_health_overview(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取所有客户健康度概览（用于管理视图）"""
    try:
        db = getattr(req.state, "db", None) or _get_db()
        org_id = getattr(req.state, "org_id", None)
        if not db or not org_id:
            return api_success(data={"customers": [], "summary": {"healthy": 0, "at_risk": 0, "churn_risk": 0}})

        tenant_id = str(org_id)
        cust_res = await db.table("customers").select("id,name,stage,estimated_value,organization_id").eq("organization_id", tenant_id).execute()
        customers = cust_res.data or []

        # Batch compute health for all customers (simplified — uses stage + value only for speed)
        summary = {"healthy": 0, "at_risk": 0, "churn_risk": 0}
        results = []
        for c in customers:
            stage_scores = {"lead": 5, "prospect": 10, "opportunity": 15, "customer": 20, "churned": 0}
            stage_score = stage_scores.get(c.get("stage", ""), 5)
            ev = float(c.get("estimated_value", 0) or 0)
            value_score = 15 if ev >= 100000 else (10 if ev >= 50000 else (5 if ev >= 10000 else 2))
            quick_score = stage_score + value_score  # Simplified — full score requires per-customer API
            risk = "healthy" if quick_score >= 25 else ("at_risk" if quick_score >= 12 else "churn_risk")
            summary[risk] = summary.get(risk, 0) + 1
            results.append({
                "id": c["id"],
                "name": c.get("name", ""),
                "stage": c.get("stage"),
                "estimated_value": ev,
                "quick_score": quick_score,
                "risk_level": risk,
            })

        return api_success(data={"customers": results, "summary": summary})
    except Exception as e:
        logger.error(f"Health overview error: err={e}")
        return api_success(data={"customers": [], "summary": {"healthy": 0, "at_risk": 0, "churn_risk": 0}})


def _get_db():
    from app.core.database import supabase
    return supabase
