import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.auth import get_current_user_id
from app.core.config import settings
from app.core.errors import ErrorCode, api_error, api_success
from app.core.trace_logger import TraceLogger
from app.models.schemas import ChatRequest
from app.services.chat_service import ChatService
from app.core.prompt_firewall import prompt_firewall
from app.services.content_moderation import check_user_input, check_user_input_advanced
from app.services.token_service import validate_request_tokens

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Chat"])


async def _error_stream(msg: str):
    import json

    yield f"data: {json.dumps({'choices': [{'delta': {'content': msg}}]}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/chat")
async def chat(request: ChatRequest, req: Request, user_id: str = Depends(get_current_user_id)):
    """
    Unified Chat Endpoint — routes all chat through LangGraph agent.

    Handles:
    - User Authentication (JWT)
    - Content Moderation (Input)
    - Token Limit Check
    - Agent System Prompt Selection
    - Streaming Response via LangGraph agent
    """

    # 1. Identity & Profile Check
    # P0 Multi-tenancy: Use scoped client from request state
    client = req.state.db
    user_res = await client.table("users").select("id, role").eq("id", user_id).maybe_single().execute()
    if not user_res.data:
        raise HTTPException(status_code=403, detail="User profile not found or access denied")

    user_role = user_res.data.get("role", "employee")

    # 2. Prompt Firewall — pre-agent input protection (G4)
    if request.messages:
        last_msg = next((m for m in reversed(request.messages) if m.role == "user"), None)
        if last_msg:
            fw_result = await prompt_firewall.scan_input(
                last_msg.content, user_id=user_id, context={"agent": request.agent}
            )
            if not fw_result.is_safe:
                return StreamingResponse(
                    _error_stream(
                        f"\u26a0\ufe0f \u5b89\u5168\u9632\u706b\u5899\u62e6\u622a: "
                        f"\u68c0\u6d4b\u5230\u98ce\u9669\u7b49\u7ea7 {fw_result.risk_level.value} "
                        f"\u7684\u5f02\u5e38\u8f93\u5165\uff0c\u8bf7\u4fee\u6539\u540e\u91cd\u8bd5\u3002"
                    ),
                    media_type="text/event-stream; charset=utf-8",
                )

    # 2b. Content Moderation (existing)
    # P2: 对带工具调用能力的高风险 Agent 启用 LLM 深度注入检测
    _tool_agents = {"approval", "crm", "admin", "data", "workflow", "kingdee", "finance"}
    if request.messages:
        last_msg = next((m for m in reversed(request.messages) if m.role == "user"), None)
        if last_msg:
            agent_type = (request.agent or "").lower()
            if agent_type in _tool_agents:
                is_safe, warning = await check_user_input_advanced(last_msg.content)
            else:
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

    # 3b. P2-9: Use settings-based mini_model (replaces fragile _infer_mini_model)
    ai_config["mini_model"] = settings.AI_MINI_MODEL

    # 4. Token Validation
    messages_dicts = []
    for m in request.messages:
        msg = {"role": m.role, "content": m.content}
        if m.image_urls:
            msg["image_urls"] = m.image_urls
        messages_dicts.append(msg)
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
    system_prompt = await ChatService.get_system_prompt(request.agent, db_client=client, org_id=org_id)

    # Trace Logger
    tracer = TraceLogger(user_id=user_id, agent=request.agent or "default")

    # 5b. Semantic Cache Check — skip LLM if high-similarity hit
    # Cache bypass logic (creative writing, error responses) is handled inside
    # SemanticCacheService.get_cache() via should_use_cache() classification.
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

    # 6. LangGraph Agentic Architecture (sole chat path)
    # Memory management (sliding window, summary, semantic cache) is handled
    # inside run_agent_stream → memory.prepare_messages, so we pass raw messages.
    from app.agent import run_agent_stream

    raw_messages = messages_dicts  # Reuse already-built list (includes image_urls)

    logger.info(f"[Chat] Using LangGraph agent for user={user_id} agent={request.agent} model={ai_config['model']}")

    return StreamingResponse(
        run_agent_stream(
            messages=raw_messages,
            config=ai_config,
            user_id=user_id,
            system_prompt=system_prompt,
            tracer=tracer,
            system_confirmed=request.system_confirmed,
            confirmed_tool=request.confirmed_tool,
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


@router.get("/tools/metadata")
async def get_tools_metadata_endpoint(req: Request, user_id: str = Depends(get_current_user_id)):
    """Return structured metadata for all tools (filtered by user role).

    Powers frontend inline actions and tool discovery UX.
    """
    client = req.state.db
    user_res = await client.table("users").select("role").eq("id", user_id).maybe_single().execute()
    user_role = (user_res.data or {}).get("role", "employee")

    from app.tools import get_tools_metadata

    metadata = get_tools_metadata(user_role)
    return api_success(data={"tools": metadata, "count": len(metadata)})


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


@router.post("/sessions/{session_id}/compact")
async def compact_session(session_id: str, req: Request, user_id: str = Depends(get_current_user_id)):
    """
    手动压缩会话上下文 — 将早期消息摘要化，保留最近的消息。
    减少 token 消耗，适合长对话场景。
    """
    client = req.state.db
    try:
        # 1. Fetch all messages in the session
        response = (
            await client.table("chat_messages")
            .select("id, role, content, created_at")
            .eq("user_id", user_id)
            .eq("session_id", session_id)
            .order("created_at", desc=False)
            .execute()
        )
        messages = response.data or []
        if len(messages) <= 6:
            return api_success(
                data={
                    "message": "会话消息较少，无需压缩。",
                    "before_count": len(messages),
                    "after_count": len(messages),
                }
            )

        # 2. Split: keep the last 6 messages, summarize the rest
        keep_count = 6
        older = messages[:-keep_count]

        # 3. Build summary of older messages
        older_text = "\n".join(
            f"[{m['role']}]: {m['content'][:500]}"
            for m in older
            if m.get("content") and m["role"] in ("user", "assistant")
        )

        if not older_text.strip():
            return api_success(
                data={
                    "message": "没有可压缩的历史消息。",
                    "before_count": len(messages),
                    "after_count": len(messages),
                }
            )

        # 4. Use mini model to generate summary
        from app.services.ai_service import AIService

        summary_prompt = (
            f"请将以下对话历史压缩为一段简洁的摘要（200字以内），保留关键信息和决策：\n\n{older_text[:3000]}"
        )
        summary = await AIService.call_llm(
            summary_prompt,
            "你是对话摘要专家。请提取关键信息，输出简洁的中文摘要。",
        )

        # 5. Delete older messages from DB
        older_ids = [m["id"] for m in older]
        for batch_start in range(0, len(older_ids), 50):
            batch = older_ids[batch_start : batch_start + 50]
            await (
                client.table("chat_messages")
                .delete()
                .eq("user_id", user_id)
                .eq("session_id", session_id)
                .in_("id", batch)
                .execute()
            )

        # 6. Insert summary as a system message at the beginning
        await (
            client.table("chat_messages")
            .insert(
                {
                    "user_id": user_id,
                    "session_id": session_id,
                    "role": "system",
                    "content": f"[对话历史摘要 — {len(older)} 条早期消息已压缩]\n{summary}",
                    "agent": "system",
                }
            )
            .execute()
        )

        return api_success(
            data={
                "message": f"已压缩 {len(older)} 条早期消息为摘要，保留最近 {keep_count} 条。",
                "before_count": len(messages),
                "after_count": keep_count + 1,
                "summary_preview": summary[:200],
            }
        )

    except Exception as e:
        logger.error(f"Failed to compact session: {e}")
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
                await (
                    client.table("starred_sessions")
                    .delete()
                    .eq("user_id", user_id)
                    .eq("session_id", session_id)
                    .execute()
                )
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
