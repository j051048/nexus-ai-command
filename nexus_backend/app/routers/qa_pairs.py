"""
QA Pairs Router - CRUD for manual Q&A annotation
"""

from fastapi import APIRouter, Depends, Request
from typing import Optional
from pydantic import BaseModel
import logging

from app.core.auth import get_current_user_id
from app.core.errors import api_success, api_error, ErrorCode
from app.models.schemas import StandardResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/qa-pairs", tags=["QA Pairs"])


# Request/Response Models
class QAPairCreate(BaseModel):
    question: str
    answer: str
    category: Optional[str] = None


class QAPairUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = None


@router.get("", response_model=StandardResponse)
async def list_qa_pairs(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    category: Optional[str] = None,
    limit: int = 100,
):
    """List all QA pairs for current user"""
    try:
        client = req.state.db
        query = client.table("qa_pairs").select("*").eq("user_id", user_id)

        if category:
            query = query.eq("category", category)

        res = await query.order("created_at", desc=True).limit(limit).execute()

        return api_success(data=res.data or [])
    except Exception as e:
        logger.error(f"Failed to list QA pairs: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("", response_model=StandardResponse)
async def create_qa_pair(
    payload: QAPairCreate, req: Request, user_id: str = Depends(get_current_user_id)
):
    """Create a new QA pair"""
    try:
        client = req.state.db

        data = {
            "question": payload.question.strip(),
            "answer": payload.answer.strip(),
            "category": payload.category.strip() if payload.category else None,
            "user_id": user_id,
        }

        res = await client.table("qa_pairs").insert(data).execute()

        if not res.data:
            raise api_error(ErrorCode.DB_ERROR, "Failed to create QA pair")

        return api_success(data=res.data[0], message="QA pair created successfully")
    except Exception as e:
        logger.error(f"Failed to create QA pair: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/{qa_id}", response_model=StandardResponse)
async def update_qa_pair(
    qa_id: str,
    payload: QAPairUpdate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Update an existing QA pair"""
    try:
        client = req.state.db

        # Build update data
        data = {}
        if payload.question is not None:
            data["question"] = payload.question.strip()
        if payload.answer is not None:
            data["answer"] = payload.answer.strip()
        if payload.category is not None:
            data["category"] = payload.category.strip() if payload.category else None

        if not data:
            return api_success(message="No updates provided")

        data["updated_at"] = "now()"

        res = (
            await client.table("qa_pairs")
            .update(data)
            .eq("id", qa_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "QA pair not found or no permission")

        return api_success(data=res.data[0], message="QA pair updated successfully")
    except Exception as e:
        logger.error(f"Failed to update QA pair: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.delete("/{qa_id}", response_model=StandardResponse)
async def delete_qa_pair(
    qa_id: str, req: Request, user_id: str = Depends(get_current_user_id)
):
    """Delete a QA pair"""
    try:
        client = req.state.db

        res = (
            await client.table("qa_pairs")
            .delete()
            .eq("id", qa_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "QA pair not found or no permission")

        return api_success(message="QA pair deleted successfully")
    except Exception as e:
        logger.error(f"Failed to delete QA pair: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/categories", response_model=StandardResponse)
async def list_categories(req: Request, user_id: str = Depends(get_current_user_id)):
    """Get all distinct categories for current user"""
    try:
        client = req.state.db

        res = (
            await client.table("qa_pairs")
            .select("category")
            .eq("user_id", user_id)
            .execute()
        )

        # Extract unique categories
        categories = set()
        for item in res.data or []:
            cat = item.get("category")
            if cat:
                categories.add(cat)

        return api_success(data=sorted(list(categories)))
    except Exception as e:
        logger.error(f"Failed to list categories: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
