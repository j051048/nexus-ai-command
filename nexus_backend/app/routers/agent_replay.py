"""
Item 45: Agent Replay API

Endpoints for replaying and comparing agent execution sessions.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.agent_replay_service import agent_replay_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent/replay", tags=["Agent Replay"])


# IMPORTANT: /compare must be defined BEFORE /{thread_id} to avoid
# FastAPI treating "compare" as a thread_id path parameter.


@router.get("/compare")
async def compare_sessions(
    request: Request,
    thread_id_a: str = Query(..., description="第一个会话的 thread_id"),
    thread_id_b: str = Query(..., description="第二个会话的 thread_id"),
    user_id: str = Depends(get_current_user_id),
):
    """对比两个会话的执行差异"""
    try:
        db = getattr(request.state, "db", None)
        result = await agent_replay_service.compare_sessions(
            thread_id_a, thread_id_b, db=db
        )
        return api_success(data=result)
    except Exception as e:
        logger.error(f"[Replay] compare_sessions error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/{thread_id}")
async def get_replay_steps(
    thread_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取指定会话的回放步骤列表"""
    try:
        db = getattr(request.state, "db", None)
        steps = await agent_replay_service.get_replay_steps(thread_id, db=db)
        if not steps:
            raise api_error(
                ErrorCode.RESOURCE_NOT_FOUND,
                f"No trace found for thread: {thread_id}",
            )
        return api_success(data={"thread_id": thread_id, "steps": steps, "total": len(steps)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Replay] get_replay_steps error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/{thread_id}/step/{step_index}")
async def get_replay_step_detail(
    thread_id: str,
    step_index: int,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取指定步骤的详细状态快照"""
    try:
        db = getattr(request.state, "db", None)
        step = await agent_replay_service.replay_step(thread_id, step_index, db=db)
        if step is None:
            raise api_error(
                ErrorCode.RESOURCE_NOT_FOUND,
                f"Step {step_index} not found in thread {thread_id}",
            )
        return api_success(data=step)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Replay] get_replay_step_detail error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
