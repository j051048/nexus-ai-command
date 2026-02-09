import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from app.core.auth import get_current_user_id
from app.core.database import supabase
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
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user_id)):
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
    # Verify user exists in DB and fetch settings
    user_res = await supabase.table("users").select("id").eq("id", user_id).maybe_single().execute()
    if not user_res.data:
        raise HTTPException(status_code=403, detail="User profile not found")

    # 2. Content Moderation
    if request.messages:
        last_msg = next((m for m in reversed(request.messages) if m.role == "user"), None)
        if last_msg:
            is_safe, warning = check_user_input(last_msg.content)
            if not is_safe:
                return StreamingResponse(_error_stream(f"⚠️ 安全拦截: {warning}"), media_type="text/event-stream")

    # 3. Load User AI Settings
    ai_config = {
        "base_url": os.getenv("AI_BASE_URL", "https://proxy.flydao.top/v1"),
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "model": "gpt-4o"
    }
    try:
        settings_res = await supabase.table("ai_settings").select("*").eq("user_id", user_id).maybe_single().execute()
        if settings_res.data:
            s = settings_res.data
            if s.get("base_url"): ai_config["base_url"] = s["base_url"]
            if s.get("key"): ai_config["api_key"] = s["key"] # Assuming 'key' or 'api_key' in DB
            if s.get("model"): ai_config["model"] = s["model"]
    except Exception as e:
        logger.warning(f"Settings fetch failed: {e}")

    if not ai_config["api_key"]:
        return StreamingResponse(_error_stream("未配置 AI API Key"), media_type="text/event-stream")

    # 4. Token Validation
    # specific validation logic...
    messages_dicts = [{"role": m.role, "content": m.content} for m in request.messages]
    is_allowed, _, limit_reason = validate_request_tokens(messages_dicts, ai_config["model"], user_id)
    if not is_allowed:
        return StreamingResponse(_error_stream(f"⚠️ 额度超限: {limit_reason}"), media_type="text/event-stream")

    # 5. Prepare Context
    system_prompt = await ChatService.get_system_prompt(request.agent)
    
    # Standardize Message History (Sliding Window)
    MAX_HISTORY = 10
    recent_messages = request.messages[-MAX_HISTORY:] if len(request.messages) > MAX_HISTORY else request.messages
    
    final_messages = [{"role": "system", "content": system_prompt}]
    for m in recent_messages:
        final_messages.append({"role": m.role, "content": m.content})
    
    # Trace Logger
    tracer = TraceLogger(user_id=user_id, agent=request.agent or "default")

    # 6. Stream Response via Service
    return StreamingResponse(
        ChatService.stream_response(final_messages, ai_config, user_id, tracer),
        media_type="text/event-stream"
    )
