import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from app.core.auth import get_current_user_id

from app.models.schemas import ChatRequest
from app.services.chat_service import ChatService
from app.services.token_service import validate_request_tokens
from app.services.content_moderation import check_user_input
from app.core.trace_logger import TraceLogger
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Chat"])


async def _error_stream(msg: str):
    import json

    yield f"data: {json.dumps({'choices': [{'delta': {'content': msg}}]})}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/chat")
async def chat(
    request: ChatRequest, req: Request, user_id: str = Depends(get_current_user_id)
):
    """
    Unified Chat Endpoint.

    Handles:
    - User Authentication (JWT)
    - Content Moderation (Input)
    - Token Limit Check
    - Agent System Prompt Selection
    - Streaming Response with Tool Execution
    """

    # 1. Identity & Profile Check
    # P0 Multi-tenancy: Use scoped client from request state
    client = req.state.db
    user_res = (
        await client.table("users")
        .select("id")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    if not user_res.data:
        raise HTTPException(
            status_code=403, detail="User profile not found or access denied"
        )

    # 2. Content Moderation
    if request.messages:
        last_msg = next(
            (m for m in reversed(request.messages) if m.role == "user"), None
        )
        if last_msg:
            is_safe, warning = check_user_input(last_msg.content)
            if not is_safe:
                return StreamingResponse(
                    _error_stream(f"⚠️ 安全拦截: {warning}"),
                    media_type="text/event-stream",
                )

    # 3. Load User AI Settings
    auth_header = req.headers.get("Authorization")
    token = (
        auth_header.split(" ")[1] if auth_header and "Bearer" in auth_header else None
    )

    ai_config = {
        "base_url": os.getenv("AI_BASE_URL", "https://proxy.flydao.top/v1"),
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "model": "gpt-4o",
        "token": token,
    }
    try:
        settings_res = (
            await client.table("ai_settings")
            .select("*")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if settings_res.data:
            s = settings_res.data
            from app.services.encryption_service import encryption_service

            if s.get("base_url"):
                ai_config["base_url"] = s["base_url"]
            if s.get("key"):
                ai_config["api_key"] = encryption_service.decrypt(s["key"])
            if s.get("model"):
                ai_config["model"] = s["model"]
    except Exception as e:
        logger.warning(f"Settings fetch failed: {e}")

    if not ai_config["api_key"]:
        return StreamingResponse(
            _error_stream("未配置 AI API Key"), media_type="text/event-stream"
        )

    # 4. Token Validation
    # specific validation logic...
    messages_dicts = [{"role": m.role, "content": m.content} for m in request.messages]
    is_allowed, _, limit_reason = validate_request_tokens(
        messages_dicts, ai_config["model"], user_id
    )
    if not is_allowed:
        return StreamingResponse(
            _error_stream(f"⚠️ 额度超限: {limit_reason}"),
            media_type="text/event-stream",
        )

    # 5. Prepare Context
    system_prompt = await ChatService.get_system_prompt(request.agent, db_client=client)

    # Standardize Message History (Sliding Window with Summary)
    MAX_HISTORY = 10
    if len(request.messages) > MAX_HISTORY:
        # Summarize older messages for context retention
        older_messages = request.messages[:-MAX_HISTORY]
        recent_messages = request.messages[-MAX_HISTORY:]

        try:
            from app.services.summary_service import summary_service

            summary = await summary_service.summarize_messages(
                [{"role": m.role, "content": m.content} for m in older_messages],
                config=ai_config,
            )
            # Insert summary as first system context
            if summary:
                from app.models.schemas import Message

                recent_messages.insert(
                    0, Message(role="system", content=f"[对话历史摘要] {summary}")
                )
        except Exception as e:
            logger.warning(f"Failed to generate conversation summary: {e}")
    else:
        recent_messages = request.messages

    final_messages = [{"role": "system", "content": system_prompt}]
    for m in recent_messages:
        final_messages.append({"role": m.role, "content": m.content})

    # Trace Logger
    tracer = TraceLogger(user_id=user_id, agent=request.agent or "default")

    # 6. Stream Response via Service
    return StreamingResponse(
        ChatService.stream_response(
            final_messages,
            ai_config,
            user_id,
            tracer,
            system_confirmed=request.system_confirmed,
            session_id=request.sessionId,
            db_client=client,
        ),
        media_type="text/event-stream",
    )


@router.get("/history/{session_id}")
async def get_chat_history(
    session_id: str, req: Request, user_id: str = Depends(get_current_user_id)
):
    """Fetch persistent chat history for a session"""
    try:
        client = req.state.db
        response = (
            await client.table("chat_messages")
            .select("*")
            .eq("user_id", user_id)
            .eq("session_id", session_id)
            .order("created_at", desc=False)
            .execute()
        )

        return {"success": True, "messages": response.data}
    except Exception as e:
        logger.error(f"Failed to fetch chat history: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch history")


@router.get("/sessions")
async def list_sessions(req: Request, user_id: str = Depends(get_current_user_id)):
    """List user's chat sessions"""
    client = req.state.db
    try:
        response = (
            await client.table("chat_messages")
            .select("session_id, agent, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        # Group by session_id, get latest message per session
        sessions = {}
        for msg in response.data or []:
            sid = msg.get("session_id", "default")
            if sid not in sessions:
                sessions[sid] = {
                    "session_id": sid,
                    "agent": msg.get("agent"),
                    "last_activity": msg.get("created_at"),
                    "message_count": 0,
                }
            sessions[sid]["message_count"] += 1

        return {"success": True, "sessions": list(sessions.values())[:50]}
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        return {"success": True, "sessions": []}


@router.delete("/sessions/{session_id}")
async def archive_session(
    session_id: str, req: Request, user_id: str = Depends(get_current_user_id)
):
    """Archive/delete a chat session"""
    client = req.state.db
    try:
        await client.table("chat_messages").delete().eq("user_id", user_id).eq(
            "session_id", session_id
        ).execute()
        return {"success": True, "message": f"Session {session_id} archived"}
    except Exception as e:
        logger.error(f"Failed to archive session: {e}")
        raise HTTPException(status_code=500, detail="Failed to archive session")


@router.get("/search")
async def search_messages(
    q: str, req: Request, user_id: str = Depends(get_current_user_id), limit: int = 20
):
    """Search chat messages by keyword"""
    if not q or len(q) < 2:
        return {"success": True, "messages": []}

    client = req.state.db
    try:
        # Simple ILIKE search on content
        response = (
            await client.table("chat_messages")
            .select("*")
            .eq("user_id", user_id)
            .ilike("content", f"%{q}%")
            .order("created_at", desc=True)
            .limit(min(limit, 50))
            .execute()
        )

        return {"success": True, "messages": response.data or []}
    except Exception as e:
        logger.error(f"Message search failed: {e}")
        return {"success": True, "messages": []}


@router.post("/sessions/{session_id}/star")
async def toggle_star_session(
    session_id: str, req: Request, user_id: str = Depends(get_current_user_id)
):
    """Toggle star/pin on a chat session"""
    client = req.state.db
    try:
        # Check if already starred (use a user_preferences or starred_sessions approach)
        # For simplicity, use a starred_sessions table or a JSON field
        # Here we'll use the chat_messages metadata approach
        existing = (
            await client.table("starred_sessions")
            .select("id")
            .eq("user_id", user_id)
            .eq("session_id", session_id)
            .maybe_single()
            .execute()
        )

        if existing.data:
            # Unstar
            await client.table("starred_sessions").delete().eq("user_id", user_id).eq(
                "session_id", session_id
            ).execute()
            return {"success": True, "starred": False}
        else:
            # Star
            await client.table("starred_sessions").insert(
                {"user_id": user_id, "session_id": session_id}
            ).execute()
            return {"success": True, "starred": True}
    except Exception as e:
        # If starred_sessions table doesn't exist, log and return gracefully
        logger.warning(f"Star session failed (table may not exist): {e}")
        return {"success": False, "message": "标星功能暂不可用"}
