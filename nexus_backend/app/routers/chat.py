from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.core.database import supabase
from app.tools import get_tool, get_all_tools_schema

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

from functools import lru_cache

@lru_cache(maxsize=1000)
def _get_cached_user_role(user_id: str) -> str:
    try:
        user_res = supabase.table("users").select("role").eq("id", user_id).maybe_single().execute()
        return user_res.data.get("role") if user_res.data else "employee"
    except:
        return "employee"

async def execute_tool(name: str, args: Dict[str, Any], current_user_id: str, config: dict = None) -> str:
    """执行具体工具逻辑并返回结果文本 (Strategy Pattern with RBAC & Caching)"""
    tool_instance = get_tool(name)
    
    if tool_instance:
        try:
            # Security Check: Role Based Access Control
            if tool_instance.required_role != "all":
                user_role = _get_cached_user_role(current_user_id)
                if tool_instance.required_role == "boss" and user_role != "boss":
                    return f"⛔ 权限拒绝: 该操作需要 [Boss/Manager] 权限，您当前的身份是 [{user_role}]。"

            return await tool_instance.run(args, current_user_id, config)
        except Exception as e:
            return f"工具 {name} 执行失败: {str(e)}"
    
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
            "tools": TOOLS if len(msgs) < 15 else None, # Heuristic: stop offering tools if conversation too deep
            "tool_choice": "auto",
            "stream": True,
            "temperature": 0.5
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", chat_endpoint, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    err = await response.aread()
                    yield f"error: {err.decode()}"
                    return
                async for line in response.aiter_lines():
                    yield line

    # Recursive loop for tool execution
    iteration = 0
    while iteration < 3: # Limit to 3 hops (P2 Fix)
        iteration += 1
        full_tool_call_json = ""
        tool_name = ""
        tool_call_id = ""
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
                    tc = delta["tool_calls"][0]
                    if tc.get("id"): 
                        tool_call_id = tc["id"]
                        if tc.get("function", {}).get("name"):
                            tool_name = tc["function"]["name"]
                    if tc.get("function", {}).get("arguments"):
                        full_tool_call_json += tc["function"]["arguments"]
                    continue

                if not has_tool_call:
                    yield f"{line}\n\n"
            except: continue

        if has_tool_call:
            try:
                args = json.loads(full_tool_call_json) if full_tool_call_json else {}
                if logger: logger.log_tool_plan(tool_name, args)
                
                tool_result = await execute_tool(tool_name, args, user_id, config=config)
                if logger: logger.log_tool_execution(tool_name, "success", tool_result)

                # Append to history for the next iteration
                messages.append({
                    "role": "assistant", 
                    "content": None, 
                    "tool_calls": [{
                        "id": tool_call_id, 
                        "type": "function", 
                        "function": {"name": tool_name, "arguments": full_tool_call_json}
                    }]
                })
                messages.append({
                    "role": "tool", 
                    "tool_call_id": tool_call_id, 
                    "name": tool_name, 
                    "content": tool_result
                })
                # Loop continues to next iteration
            except Exception as e:
                yield f"data: {json.dumps({'choices': [{'delta': {'content': f' Tool Error: {str(e)}'}}]})}\n\n"
                break
        else:
            # No more tool calls, we are done
            break

    if logger: logger.log_end()
    yield "data: [DONE]\n\n"


@router.post("/chat")
async def chat(request: ChatRequest, x_user_id: Optional[str] = Header(None)):
    # P0 Security: Validate user existence and prefer header
    user_id = x_user_id or request.userId
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication Required (Missing User ID)")
    
    # Verify user exists in DB
    user_check = supabase.table("users").select("id").eq("id", user_id).maybe_single().execute()
    if not user_check.data:
        raise HTTPException(status_code=403, detail="Unauthorized: User does not exist")

    ai_config = {
        "base_url": "https://proxy.flydao.top/v1",
        "api_key": "",
        "model": "gpt-4o-mini"
    }

    try:
        response = supabase.table("ai_settings").select("*").eq("user_id", user_id).maybe_single().execute()
        if response.data:
            settings = response.data
            ai_config["base_url"] = settings.get("base_url") or ai_config["base_url"]
            ai_config["api_key"] = settings.get("api_key") or ""
            ai_config["model"] = settings.get("model") or ai_config["model"]
    except Exception as e:
        print(f"Failed to fetch user settings: {e}")

    if not ai_config["api_key"]:
        return StreamingResponse(_error_stream("请先在系统设置中配置您的 API Key"), media_type="text/event-stream")

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
    
    formatted_messages = [{"role": "system", "content": system_prompt + coref_instruction}]
    for msg in request.messages:
        formatted_messages.append({"role": msg.role, "content": msg.content})

    return StreamingResponse(
        stream_openai_response(formatted_messages, ai_config, user_id, tracer),
        media_type="text/event-stream"
    )

async def _error_stream(msg: str):
    yield f"data: {json.dumps({'choices': [{'delta': {'content': msg}}]})}\n\n"
    yield "data: [DONE]\n\n"
