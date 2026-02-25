import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.core.trace_logger import TraceLogger
from app.models.schemas import ChatRequest
from app.services.chat_service import ChatService
from app.services.content_moderation import check_user_input
from app.services.token_service import validate_request_tokens

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Chat"])

# ── Feature Flag: LangGraph Agent ──────────────────────────────────────────
# Set USE_LANGGRAPH_AGENT=true in env to enable the new agentic architecture.
# When disabled, falls back to the legacy ChatService.stream_response.
USE_LANGGRAPH_AGENT = os.getenv("USE_LANGGRAPH_AGENT", "true").lower() in ("true", "1", "yes")


def _infer_mini_model(model: str) -> str:
    """Infer the lightweight model variant for simple queries."""
    _mini_map = {
        "gpt-4o": "gpt-4o-mini",
        "gpt-4": "gpt-4o-mini",
        "gpt-4-turbo": "gpt-4o-mini",
        "gpt-3.5-turbo": "gpt-3.5-turbo",
        "gpt-4o-mini": "gpt-4o-mini",
    }
    return _mini_map.get(model, f"{model}-mini" if "mini" not in model else model)


async def _error_stream(msg: str):
    import json

    yield f"data: {json.dumps({'choices': [{'delta': {'content': msg}}]}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/chat")
async def chat(request: ChatRequest, req: Request, user_id: str = Depends(get_current_user_id)):
    """
    Unified Chat Endpoint.

    Handles:
    - User Authentication (JWT)
    - Content Moderation (Input)
    - Token Limit Check
    - Agent System Prompt Selection
    - Streaming Response via LangGraph agent (or legacy ChatService fallback)
    """

    # 1. Identity & Profile Check
    # P0 Multi-tenancy: Use scoped client from request state
    client = req.state.db
    user_res = await client.table("users").select("id, role").eq("id", user_id).maybe_single().execute()
    if not user_res.data:
        raise HTTPException(status_code=403, detail="User profile not found or access denied")

    user_role = user_res.data.get("role", "employee")

    # 2. Content Moderation
    if request.messages:
        last_msg = next((m for m in reversed(request.messages) if m.role == "user"), None)
        if last_msg:
            is_safe, warning = check_user_input(last_msg.content)
            if not is_safe:
                return StreamingResponse(
                    _error_stream(f"⚠️ 安全拦截: {warning}"),
                    media_type="text/event-stream; charset=utf-8",
                )

    # 3. Load User AI Settings
    auth_header = req.headers.get("Authorization")
    token = auth_header.split(" ")[1] if auth_header and "Bearer" in auth_header else None

    ai_config = {
        "base_url": os.getenv("AI_BASE_URL", "https://proxy.flydao.top/v1"),
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "model": "gpt-4o",
        "token": token,
    }
    try:
        # Query AI settings with organization_id to match frontend save logic
        org_id = getattr(req.state, "org_id", None)
        settings_query = client.table("ai_settings").select("*").eq("user_id", user_id)
        if org_id:
            settings_query = settings_query.eq("organization_id", org_id)
        settings_res = await settings_query.maybe_single().execute()
        if settings_res.data:
            s = settings_res.data
            from app.services.encryption_service import encryption_service

            if s.get("base_url"):
                user_base_url = s["base_url"].rstrip("/")
                # Users often save the full endpoint URL from the test panel
                # (e.g. https://api.apiyi.com/v1/chat/completions), but OpenAI
                # SDK / LangChain expects the base URL without /chat/completions
                # since they append that path automatically.
                if user_base_url.endswith("/chat/completions"):
                    user_base_url = user_base_url[: -len("/chat/completions")]
                ai_config["base_url"] = user_base_url
            if s.get("api_key"):
                try:
                    ai_config["api_key"] = encryption_service.decrypt(s["api_key"])
                except Exception:
                    logger.warning("API key decryption failed, key may be corrupted")
                    ai_config["api_key"] = ""
            if s.get("model"):
                ai_config["model"] = s["model"]
    except Exception as e:
        logger.warning(f"Settings fetch failed: {e}")

    if not ai_config["api_key"]:
        return StreamingResponse(_error_stream("未配置 AI API Key"), media_type="text/event-stream; charset=utf-8")

    # 3b. Infer mini_model for dynamic routing
    ai_config["mini_model"] = _infer_mini_model(ai_config["model"])

    # 4. Token Validation
    messages_dicts = [{"role": m.role, "content": m.content} for m in request.messages]
    is_allowed, _, limit_reason = validate_request_tokens(messages_dicts, ai_config["model"], user_id)
    if not is_allowed:
        return StreamingResponse(
            _error_stream(f"⚠️ 额度超限: {limit_reason}"),
            media_type="text/event-stream; charset=utf-8",
        )

    # 4b. P0 Fix: Tenant Quota Enforcement
    org_id = getattr(req.state, "org_id", None)
    if org_id:
        from app.services.tenant_credit_service import CreditType, tenant_credit_service

        has_credit, credit_error = await tenant_credit_service.check_credit(org_id, CreditType.API_CALLS, 1, db=client)
        if not has_credit:
            return StreamingResponse(
                _error_stream(f"⚠️ 组织配额不足: {credit_error}"),
                media_type="text/event-stream; charset=utf-8",
            )

    # 5. Prepare Context
    system_prompt = await ChatService.get_system_prompt(request.agent, db_client=client)

    # Trace Logger
    tracer = TraceLogger(user_id=user_id, agent=request.agent or "default")

    # 5b. P1 Fix: Semantic Cache Check — skip LLM if high-similarity hit
    last_user_msg = next((m.content for m in reversed(request.messages) if m.role == "user"), None)
    if last_user_msg:
        try:
            from app.services.semantic_cache import semantic_cache_service

            cached = await semantic_cache_service.get_cache(last_user_msg, user_id)
            if cached:
                logger.info(f"[Chat] Semantic cache hit for user={user_id}")

                async def _cache_stream(text: str):
                    import json

                    yield f"data: {json.dumps({'choices': [{'delta': {'content': text}}]})}\n\n"
                    yield "data: [DONE]\n\n"

                return StreamingResponse(_cache_stream(cached), media_type="text/event-stream; charset=utf-8")
        except Exception as e:
            logger.debug(f"Semantic cache check skipped: {e}")

    # 6. Route to LangGraph agent or legacy ChatService
    if USE_LANGGRAPH_AGENT:
        # ── New: LangGraph Agentic Architecture ──
        # Memory management (sliding window, summary, semantic cache) is handled
        # inside run_agent_stream → memory.prepare_messages, so we pass raw messages.
        from app.agent import run_agent_stream

        raw_messages = [{"role": m.role, "content": m.content} for m in request.messages]

        logger.info(
            f"[Chat] Using LangGraph agent for user={user_id} " f"agent={request.agent} model={ai_config['model']}"
        )

        return StreamingResponse(
            run_agent_stream(
                messages=raw_messages,
                config=ai_config,
                user_id=user_id,
                system_prompt=system_prompt,
                tracer=tracer,
                system_confirmed=request.system_confirmed,
                session_id=request.sessionId,
                db_client=client,
                agent_name=request.agent,
                user_role=user_role,
                org_id=org_id,
                # VMD extensions: pass scene/agent codes for role-based routing
                scene_code=request.scene_code,
                vmd_agent_code=request.agent_code,
            ),
            media_type="text/event-stream; charset=utf-8",
        )
    else:
        # ── Legacy: ChatService.stream_response ──
        # Keep the old sliding window + summary logic for backward compatibility
        logger.info(f"[Chat] Using legacy ChatService for user={user_id} " f"agent={request.agent}")

        max_history = 10
        if len(request.messages) > max_history:
            older_messages = request.messages[:-max_history]
            recent_messages = request.messages[-max_history:]

            try:
                from app.services.summary_service import summary_service

                summary = await summary_service.summarize_messages(
                    [{"role": m.role, "content": m.content} for m in older_messages],
                    config=ai_config,
                )
                if summary:
                    from app.models.schemas import Message

                    recent_messages.insert(0, Message(role="system", content=f"[对话历史摘要] {summary}"))
            except Exception as e:
                logger.warning(f"Failed to generate conversation summary: {e}")
        else:
            recent_messages = request.messages

        final_messages = [{"role": "system", "content": system_prompt}]
        for m in recent_messages:
            final_messages.append({"role": m.role, "content": m.content})

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
            media_type="text/event-stream; charset=utf-8",
        )


@router.get("/history/{session_id}")
async def get_chat_history(session_id: str, req: Request, user_id: str = Depends(get_current_user_id)):
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

        return api_success(data={"messages": response.data})
    except Exception as e:
        logger.error(f"Failed to fetch chat history: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


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
            .limit(500)
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

        return api_success(data={"sessions": list(sessions.values())[:50]})
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        return api_success(data={"sessions": []})


@router.delete("/sessions/{session_id}")
async def archive_session(session_id: str, req: Request, user_id: str = Depends(get_current_user_id)):
    """Archive/delete a chat session"""
    client = req.state.db
    try:
        await client.table("chat_messages").delete().eq("user_id", user_id).eq("session_id", session_id).execute()
        return api_success(data={"message": f"Session {session_id} archived"})
    except Exception as e:
        # PostgREST 204 = success with no content body
        if hasattr(e, "code") and str(getattr(e, "code", "")) == "204":
            return api_success(data={"message": f"Session {session_id} archived"})
        logger.error(f"Failed to archive session: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/search")
async def search_messages(q: str, req: Request, user_id: str = Depends(get_current_user_id), limit: int = 20):
    """Search chat messages by keyword"""
    if not q or len(q) < 2:
        return api_success(data={"messages": []})

    client = req.state.db
    try:
        # P1 Security: Escape LIKE wildcards in user input to prevent wildcard injection
        escaped_q = q.replace("%", r"\%").replace("_", r"\_")
        # Simple ILIKE search on content
        response = (
            await client.table("chat_messages")
            .select("*")
            .eq("user_id", user_id)
            .ilike("content", f"%{escaped_q}%")
            .order("created_at", desc=True)
            .limit(min(limit, 50))
            .execute()
        )

        return api_success(data={"messages": response.data or []})
    except Exception as e:
        logger.error(f"Message search failed: {e}")
        return api_success(data={"messages": []})


@router.post("/sessions/{session_id}/star")
async def toggle_star_session(session_id: str, req: Request, user_id: str = Depends(get_current_user_id)):
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
            try:
                await client.table("starred_sessions").delete().eq("user_id", user_id).eq(
                    "session_id", session_id
                ).execute()
            except Exception as del_e:
                if not (hasattr(del_e, "code") and str(getattr(del_e, "code", "")) == "204"):
                    raise
            return api_success(data={"starred": False})
        else:
            # Star
            await client.table("starred_sessions").insert({"user_id": user_id, "session_id": session_id}).execute()
            return api_success(data={"starred": True})
    except Exception as e:
        # If starred_sessions table doesn't exist, log and return gracefully
        logger.warning(f"Star session failed (table may not exist): {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "标星功能暂不可用")
