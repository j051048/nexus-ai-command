"""AI Feedback API - Collect user feedback on AI responses."""

import logging

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_list, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ai/feedback", tags=["AI Feedback"])


class FeedbackRequest(BaseModel):
    session_id: str = Field(..., description="会话ID")
    message_index: int = Field(0, description="消息索引")
    rating: str = Field(..., description="评价: positive/negative")
    comment: str | None = Field(None, max_length=1000, description="评价备注")
    ai_response_snippet: str | None = Field(None, max_length=500, description="AI回复片段")
    query_snippet: str | None = Field(None, max_length=500, description="用户问题片段")


@router.post("")
async def submit_feedback(
    body: FeedbackRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """提交AI回复反馈"""
    try:
        if body.rating not in ("positive", "negative"):
            return api_error(ErrorCode.VALIDATION_INVALID_INPUT, "rating must be 'positive' or 'negative'")

        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        org_id = getattr(req.state, "org_id", None)
        record = {
            "tenant_id": org_id,
            "user_id": user_id,
            "session_id": body.session_id,
            "message_index": body.message_index,
            "rating": body.rating,
            "comment": body.comment,
            "ai_response_snippet": body.ai_response_snippet,
            "query_snippet": body.query_snippet,
        }

        res = await client.table("ai_feedback").insert(record).execute()
        feedback = res.data[0] if res.data else record

        logger.info("AI feedback received: user=%s rating=%s session=%s", user_id, body.rating, body.session_id)
        return api_success(data={"feedback": feedback}, message="反馈已记录")
    except Exception as e:
        logger.error("Submit feedback error: %s", e)
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("")
async def list_feedback(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    rating: str | None = Query(None, description="按评价筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取反馈列表"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        org_id = getattr(req.state, "org_id", None)
        query = (
            client.table("ai_feedback")
            .select("*", count="exact")
            .order("created_at", desc=True)
        )
        if org_id:
            query = query.eq("tenant_id", org_id)
        if rating:
            query = query.eq("rating", rating)

        offset = (page - 1) * page_size
        query = query.range(offset, offset + page_size - 1)

        res = await query.execute()
        total = res.count if res.count is not None else 0
        return api_list(items=res.data or [], total=total, page=page, page_size=page_size)
    except Exception as e:
        logger.error("List feedback error: %s", e)
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/stats")
async def feedback_stats(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    days: int = Query(30, ge=1, le=90),
):
    """获取反馈统计"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        from datetime import UTC, datetime, timedelta
        org_id = getattr(req.state, "org_id", None)
        since = (datetime.now(UTC) - timedelta(days=days)).isoformat()

        base = client.table("ai_feedback").select("rating")
        if org_id:
            base = base.eq("tenant_id", org_id)
        base = base.gte("created_at", since)

        res = await base.execute()
        feedbacks = res.data or []

        positive = sum(1 for f in feedbacks if f.get("rating") == "positive")
        negative = sum(1 for f in feedbacks if f.get("rating") == "negative")
        total = positive + negative

        return api_success(data={
            "total": total,
            "positive": positive,
            "negative": negative,
            "satisfaction_rate": round(positive / total * 100, 1) if total > 0 else 0,
            "days": days,
        })
    except Exception as e:
        logger.error("Feedback stats error: %s", e)
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
