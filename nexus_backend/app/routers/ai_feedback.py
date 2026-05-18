"""AI feedback routes."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

router = APIRouter(prefix="/api/ai-feedback", tags=["AI Feedback"])
router_v1 = APIRouter(prefix="/api/v1/ai", tags=["AI Feedback"])


class AIFeedbackIn(BaseModel):
    session_id: str | None = None
    message_index: int | None = None
    rating: str
    comment: str | None = None
    ai_response_snippet: str | None = None
    query_snippet: str | None = None
    metadata: dict | None = None


async def _record_feedback(body: AIFeedbackIn, request: Request, user_id: str):
    if body.rating not in {"positive", "negative"}:
        raise api_error(
            ErrorCode.VALIDATION_INVALID_INPUT,
            "rating must be positive or negative",
        )
    db = getattr(request.state, "db", None)
    if not db:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "Database unavailable")

    org_id = getattr(request.state, "org_id", None)
    row = {
        "tenant_id": org_id,
        "user_id": user_id,
        "session_id": body.session_id,
        "message_index": body.message_index,
        "rating": body.rating,
        "comment": (body.comment or "")[:2000] if body.comment else None,
        "ai_response_snippet": (
            (body.ai_response_snippet or "")[:1000]
            if body.ai_response_snippet
            else None
        ),
        "query_snippet": (
            (body.query_snippet or "")[:1000] if body.query_snippet else None
        ),
        "metadata": body.metadata or {},
    }
    result = await db.table("ai_feedback").insert(row).execute()

    if body.rating == "negative" and body.query_snippet:
        from app.services.eval_case_promotion_service import (
            eval_case_promotion_service,
        )

        case = eval_case_promotion_service.build_case_from_failure(
            {
                "organization_id": org_id,
                "user_message": body.query_snippet,
                "error_type": "negative_feedback",
                "error_detail": body.ai_response_snippet or body.comment or "",
                "pattern_key": "negative_feedback:user_reported",
            }
        )
        await db.table("agent_eval_cases").upsert(
            [case.to_row()],
            on_conflict="source_type,source_ref",
        ).execute()

    return api_success(data={"feedback": (result.data or [row])[0]})


@router.post("")
async def record_feedback(
    body: AIFeedbackIn,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return await _record_feedback(body, request, user_id)


@router_v1.post("/feedback")
async def record_feedback_v1(
    body: AIFeedbackIn,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return await _record_feedback(body, request, user_id)
