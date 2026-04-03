"""AI 业务上下文聚合 API - 按场景返回相关业务数据"""

import logging

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/context", tags=["BusinessContext"])

VALID_SCENES = {"approval", "sales", "boss", "performance", "default"}


async def _safe_query(db, table: str, select: str, org_id: str, extra_filters: dict | None = None, order_by: str | None = None, limit: int | None = None):
    """安全查询封装，失败返回空列表而非抛异常"""
    try:
        query = db.table(table).select(select).eq("organization_id", org_id)
        if extra_filters:
            for key, value in extra_filters.items():
                query = query.eq(key, value)
        if order_by:
            query = query.order(order_by, desc=True)
        if limit:
            query = query.limit(limit)
        result = await query.execute()
        return result.data or []
    except Exception as e:
        logger.warning(f"Context query failed for {table}: {e}")
        return []


@router.get("/business")
async def get_business_context(
    req: Request,
    scene: str = Query("default", description="场景: approval|sales|boss|performance|default"),
    user_id: str = Depends(get_current_user_id),
):
    """根据场景聚合返回相关业务数据"""
    try:
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")

        if scene not in VALID_SCENES:
            raise api_error(ErrorCode.VALIDATION_MISSING_FIELD, f"无效的 scene: {scene}，可选值: {', '.join(VALID_SCENES)}")

        context = {"scene": scene}

        if scene == "approval":
            context["pending_approvals"] = await _safe_query(
                db, "oa_leave_requests", "*", org_id,
                extra_filters={"status": "pending"},
                order_by="created_at", limit=20,
            )
            context["my_approvals"] = await _safe_query(
                db, "oa_leave_requests", "*", org_id,
                extra_filters={"user_id": user_id},
                order_by="created_at", limit=10,
            )

        elif scene == "sales":
            context["leads"] = await _safe_query(
                db, "sales_leads", "*", org_id,
                order_by="created_at", limit=20,
            )
            context["metrics"] = await _safe_query(
                db, "sales_metrics", "*", org_id,
            )
            context["targets"] = await _safe_query(
                db, "sales_targets", "*", org_id,
            )

        elif scene == "boss":
            context["pending_approvals"] = await _safe_query(
                db, "oa_leave_requests", "*", org_id,
                extra_filters={"status": "pending"},
                order_by="created_at", limit=20,
            )
            context["team_members"] = await _safe_query(
                db, "users", "id, name, role, score, total_bonus", org_id,
                limit=50,
            )
            context["metrics"] = await _safe_query(
                db, "sales_metrics", "*", org_id,
            )
            context["projects"] = await _safe_query(
                db, "projects", "*", org_id,
                order_by="created_at", limit=20,
            )

        elif scene == "performance":
            context["team_members"] = await _safe_query(
                db, "users", "id, name, role, score, total_bonus", org_id,
                limit=50,
            )
            context["projects"] = await _safe_query(
                db, "projects", "*", org_id,
                order_by="created_at", limit=20,
            )

        else:  # default
            context["projects"] = await _safe_query(
                db, "projects", "*", org_id,
                order_by="created_at", limit=10,
            )
            context["pending_approvals"] = await _safe_query(
                db, "oa_leave_requests", "*", org_id,
                extra_filters={"status": "pending"},
                order_by="created_at", limit=10,
            )
            context["notifications"] = await _safe_query(
                db, "notifications", "*", org_id,
                extra_filters={"user_id": user_id, "read": False},
                order_by="created_at", limit=10,
            )
            context["my_tasks"] = await _safe_query(
                db, "oa_tasks", "*", org_id,
                extra_filters={"assignee_id": user_id},
                order_by="created_at", limit=10,
            )

        return api_success(data=context)
    except Exception as e:
        logger.error(f"Failed to get business context (scene={scene}): {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取业务上下文失败")
