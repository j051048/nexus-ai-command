import asyncio
import json
import httpx
import time
import os
from fastapi import APIRouter, Header, HTTPException, Depends
from fastapi.responses import StreamingResponse
from app.core.auth import get_current_user_id
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.core.database import supabase
from app.tools import get_tool, get_all_tools_schema
from app.services.cache_service import cache_service
from app.services.token_service import token_counter, usage_tracker, validate_request_tokens, record_completion
from app.services.content_moderation import content_moderator, check_user_input, sanitize_output

router = APIRouter(prefix="/api", tags=["Chat"])

class Message(BaseModel):
    role: str
    content: str
    id: Optional[str] = None
    timestamp: Optional[str] = None
    agent: Optional[str] = None

class ChatRequest(BaseModel):
    messages: List[Message]
    agent: Optional[str] = None
    userId: Optional[str] = None # Keeping for compatibility but favoring header

# --- 工具定义 (Strategy Pattern) ---
TOOLS = get_all_tools_schema()

# P1 Optimization: Use distributed cache service instead of in-memory cache
async def _get_cached_user_role(user_id: str) -> str:
    """Get user role with distributed cache support"""
    # Try cache first
    cached_role = await cache_service.get_user_role(user_id)
    if cached_role:
        return cached_role
    
    # Fetch from database
    try:
        user_res = await supabase.table("users").select("role").eq("id", user_id).maybe_single().execute()
        role = user_res.data.get("role") if user_res.data else "employee"
        # Cache the result
        await cache_service.set_user_role(user_id, role)
        return role
    except Exception as e:
        print(f"Error fetching user role: {e}")
        return "employee"

async def execute_tool(name: str, args: Dict[str, Any], current_user_id: str, config: dict = None) -> str:
    """执行具体工具逻辑并带重试 (Strategy Pattern with RBAC & Retry)"""
    tool_instance = get_tool(name)
    
    if tool_instance:
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                # Security Check: Role Based Access Control
                required_role = tool_instance.required_role
                
                if required_role != "all":
                    user_role = await _get_cached_user_role(current_user_id)
                    
                    # Boss-only tools
                    if required_role == "boss" and user_role not in ["boss", "founder"]:
                        return f"⛔ 权限拒绝: 该操作需要 [Boss/Manager] 权限，您当前的身份是 [{user_role}]。"
                    
                    # AI Assistant tools - 允许所有用户通过 AI 调用这些工具
                    # 工具内部会验证 employee_id 参数
                    # ai_assistant 角色的工具可以被任何人通过 chat 调用
                    # 因为这些工具会代表用户执行操作，而不是赋予用户特权
                    if required_role == "ai_assistant":
                        # 这些工具的安全性由工具内部逻辑保证
                        # 例如：submit_approval_on_behalf 会验证 employee_id 并设置正确的 submitted_by
                        pass  # 允许执行

                return await tool_instance.run(args, current_user_id, config)
            except Exception as e:
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1)) # Backoff
                    continue
                return f"工具 {name} 在 {max_retries+1} 次尝试后执行失败: {str(e)}"
    
    return f"未知工具或工具未注册: {name}"

async def stream_openai_response(messages: List[dict], config: dict, user_id: str, logger: Any):
    """
    Stream response from OpenAI with recursive tool use support (P2 Fix)
    """
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    model = config.get("model")

    target_url = base_url.split("/chat/completions")[0].rstrip("/")
    if not (target_url.endswith("/v1") or "/v1" in target_url):
        target_url = f"{target_url}/v1"
    chat_endpoint = f"{target_url}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    if logger: logger.log_start(messages)

    async def _get_stream(msgs):
        payload = {
            "model": model,
            "messages": msgs,
            "tools": TOOLS if len(msgs) < 20 else None, 
            "tool_choice": "auto",
            "stream": True,
            "temperature": 0.5
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", chat_endpoint, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        err = await response.aread()
                        yield f"error: AI服务响应异常 ({response.status_code}) - {err.decode()[:200]}"
                        return
                    async for line in response.aiter_lines():
                        yield line
        except Exception as e:
            yield f"error: 连接AI服务失败 - {str(e)}"

    # Recursive loop for tool execution
    iteration = 0
    while iteration < 5: # Support deeper chains (TC-02)
        iteration += 1
        # tool_calls_map: tool_index -> {id: str, name: str, args: str}
        tool_calls_map = {} 
        has_tool_call = False
        
        async for line in _get_stream(messages):
            if line.startswith("error: "):
                yield f"data: {json.dumps({'choices': [{'delta': {'content': f' Error: {line[7:]}'}}]})}\n\n"
                return
            if not line.startswith("data: "): continue
            line_data = line[6:].strip()
            if line_data == "[DONE]": break
            
            try:
                parsed = json.loads(line_data)
                if not parsed['choices']: continue
                delta = parsed['choices'][0]['delta']
                
                if "tool_calls" in delta:
                    has_tool_call = True
                    for tool_call in delta["tool_calls"]:
                        idx = tool_call.get("index", 0)
                        if idx not in tool_calls_map:
                            tool_calls_map[idx] = {"id": "", "name": "", "args": ""}
                        
                        if tool_call.get("id"): tool_calls_map[idx]["id"] = tool_call["id"]
                        if tool_call.get("function", {}).get("name"): 
                            tool_calls_map[idx]["name"] = tool_call["function"]["name"]
                        if tool_call.get("function", {}).get("arguments"):
                            tool_calls_map[idx]["args"] += tool_call["function"]["arguments"]
                    continue

                if not has_tool_call:
                    yield f"{line}\n\n"
            except: continue

        if has_tool_call:
            try:
                # 1. Capture Assistant Call in history
                # This will be added to messages AFTER all tool results are gathered.
                
                # 2. Execute tools and gather results
                tool_results_list = []
                for idx in sorted(tool_calls_map.keys()):
                    call = tool_calls_map[idx]
                    t_name = call["name"]
                    t_id = call["id"]
                    try:
                        t_args = json.loads(call["args"]) if call["args"] else {}
                    except json.JSONDecodeError:
                        t_args = {} # Handle malformed JSON arguments
                        tool_results_list.append({
                            "tool_call_id": t_id,
                            "name": t_name,
                            "content": f"Error: 工具 {t_name} 的参数解析失败: {call['args']}"
                        })
                        if logger: logger.log_tool_execution(t_name, "failed", tool_results_list[-1]["content"])
                        continue
                    
                    if logger: logger.log_tool_plan(t_name, t_args)
                    
                    try:
                        tool_result_content = await asyncio.wait_for(
                            execute_tool(t_name, t_args, user_id, config=config),
                            timeout=30.0
                        )
                        tool_results_list.append({
                            "tool_call_id": t_id,
                            "name": t_name,
                            "content": tool_result_content
                        })
                        if logger: logger.log_tool_execution(t_name, "success" if "Error" not in tool_result_content else "failed", tool_result_content)
                    except asyncio.TimeoutError:
                        tool_result_content = f"Error: 工具 {t_name} 执行超时。"
                        tool_results_list.append({
                            "tool_call_id": t_id,
                            "name": t_name,
                            "content": tool_result_content
                        })
                        if logger: logger.log_tool_execution(t_name, "failed", tool_result_content)
                    except Exception as e:
                        tool_result_content = f"Error: 工具 {t_name} 执行出错: {str(e)}"
                        tool_results_list.append({
                            "tool_call_id": t_id,
                            "name": t_name,
                            "content": tool_result_content
                        })
                        if logger: logger.log_tool_execution(t_name, "failed", tool_result_content)
                
                # REFACTORED LOOP for history:
                # Correct Sequence: [ASSISTANT w/ tool_calls list], [TOOL res 1], [TOOL res 2]...
                history_assistant = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["args"]}}
                        for c in tool_calls_map.values()
                    ]
                }
                messages.append(history_assistant)
                
                for res in tool_results_list:
                    messages.append({
                        "role": "tool", 
                        "tool_call_id": res["tool_call_id"], 
                        "name": res["name"], 
                        "content": res["content"]
                    })
            except Exception as e:
                yield f"data: {json.dumps({'choices': [{'delta': {'content': f' Tool Orchestration Error: {str(e)}'}}]})}\n\n"
                break
        else:
            # No more tool calls, we are done
            break

    if logger: logger.log_end()
    yield "data: [DONE]\n\n"


@router.post("/chat")
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user_id)):
    """
    P0 Fix: Identity verification via JWT.
    P1 Enhancement: Token counting, content moderation, and usage tracking.
    """
    # Verify user exists in DB
    user_check = await supabase.table("users").select("id").eq("id", user_id).maybe_single().execute()
    if not user_check.data:
        raise HTTPException(status_code=403, detail="Unauthorized: User identity verified but profile missing in system DB")
    
    # P1: Content moderation - check last user message for injection attempts
    if request.messages:
        last_user_msg = next((m for m in reversed(request.messages) if m.role == "user"), None)
        if last_user_msg:
            is_safe, warning = check_user_input(last_user_msg.content)
            if not is_safe:
                return StreamingResponse(
                    _error_stream(f"⚠️ 安全检查未通过: {warning}"),
                    media_type="text/event-stream"
                )

    ai_config = {
        "base_url": os.getenv("AI_BASE_URL", "https://proxy.flydao.top/v1"),
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "model": "gpt-4o"
    }

    try:
        response = await supabase.table("ai_settings").select("*").eq("user_id", user_id).maybe_single().execute()
        if response.data:
            settings = response.data
            # Only override if the user has explicitly set a value
            if settings.get("base_url"): ai_config["base_url"] = settings.get("base_url")
            if settings.get("api_key"): ai_config["api_key"] = settings.get("api_key")
            if settings.get("model"): ai_config["model"] = settings.get("model")
    except Exception as e:
        print(f"Failed to fetch user settings: {e}")

    if not ai_config["api_key"]:
        return StreamingResponse(_error_stream("系统未配置 OpenAI API Key，请联系管理员或在设置中添加私有 Key"), media_type="text/event-stream")
    
    # P1: Token counting and usage limit check
    messages_for_count = [{"role": m.role, "content": m.content} for m in request.messages]
    is_allowed, token_count, limit_reason = validate_request_tokens(
        messages_for_count, 
        ai_config["model"], 
        user_id
    )
    if not is_allowed:
        return StreamingResponse(
            _error_stream(f"⚠️ 使用限制: {limit_reason}。请稍后再试或联系管理员。"),
            media_type="text/event-stream"
        )

    from app.core.prompts_registry import SYSTEM_PROMPTS
    import datetime
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if request.agent == "@销售指挥官":
        raw_prompt = SYSTEM_PROMPTS["sales_commander"]
    elif request.agent == "@审批管家":
        raw_prompt = SYSTEM_PROMPTS["approval_manager"]
    elif request.agent == "@绩效教练":
        raw_prompt = SYSTEM_PROMPTS["performance_coach"]
    else:
        raw_prompt = SYSTEM_PROMPTS["default_fallback"]
    
    try:
        system_prompt = raw_prompt.format(current_time=now_str)
    except:
        system_prompt = raw_prompt
    
    from app.core.trace_logger import TraceLogger
    tracer = TraceLogger(user_id=user_id, agent=request.agent or "default")

    coref_instruction = "\nIMPORTANT: When using tools like 'query_knowledge_base', you MUST generate a standalone, explicit search query. Do NOT use pronouns. Replace them with specific names from history."
    
    # BUG-01 Fix: Context Slicing (Sliding Window) 
    # Keep only the last 10 messages to prevent Token/Context window overflow.
    # We always keep the System Prompt at index 0.
    MAX_HISTORY = 10
    user_messages = request.messages[-MAX_HISTORY:] if len(request.messages) > MAX_HISTORY else request.messages
    
    formatted_messages = [{"role": "system", "content": system_prompt + coref_instruction}]
    for msg in user_messages:
        formatted_messages.append({"role": msg.role, "content": msg.content})

    return StreamingResponse(
        stream_openai_response(formatted_messages, ai_config, user_id, tracer),
        media_type="text/event-stream"
    )

async def _error_stream(msg: str):
    yield f"data: {json.dumps({'choices': [{'delta': {'content': msg}}]})}\n\n"
    yield "data: [DONE]\n\n"
