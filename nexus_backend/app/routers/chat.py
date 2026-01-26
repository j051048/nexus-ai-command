from app.services.vector_service import vector_service
import json
import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.core.database import supabase
from app.core.prompts import prompts
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
    userId: Optional[str] = None

# --- 工具定义 (Strategy Pattern) ---
# P0 Completed: Tool definitions are now fully dynamic
TOOLS = get_all_tools_schema()

async def execute_tool(name: str, args: Dict[str, Any], current_user_id: str, config: dict = None) -> str:
    """执行具体工具逻辑并返回结果文本 (Strategy Pattern with RBAC)"""
    tool_instance = get_tool(name)
    
    if tool_instance:
        try:
            # 1. Security Check: Role Based Access Control
            if tool_instance.required_role != "all":
                # Fetch user role from DB
                user_res = supabase.table("users").select("role").eq("id", current_user_id).maybe_single().execute()
                user_role = user_res.data.get("role") if user_res.data else "employee"
                
                # Simple check: 'boss' tools require 'boss' role
                # Expand logic here for more complex hierarchies (e.g. manager)
                if tool_instance.required_role == "boss" and user_role != "boss":
                    return f"⛔ 权限拒绝: 该操作需要 [Boss/Manager] 权限，您当前的身份是 [{user_role}]。"

            # 2. Execute
            return await tool_instance.run(args, current_user_id, config)
        except Exception as e:
            return f"工具 {name} 执行失败: {str(e)}"
    
    return f"未知工具或工具未注册: {name}"

async def stream_openai_response(messages: List[dict], config: dict, user_id: str):
    """
    Stream response from OpenAI with tool use support
    """
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    model = config.get("model")

    # URL Normalization: Ensure we have the base endpoint without /chat/completions
    target_url = base_url.split("/chat/completions")[0].rstrip("/")
    if not target_url.endswith("/v1") and "/v1" not in target_url:
        target_url = f"{target_url}/v1"
    
    chat_endpoint = f"{target_url}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "PostmanRuntime/7.26.8" # Pretend to be Postman or standard Setup
    }

    payload = {
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "stream": True,
        "temperature": 0.5
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            async with client.stream("POST", chat_endpoint, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    error_content = await response.aread()
                    yield f"data: {json.dumps({'choices': [{'delta': {'content': f' Error {response.status_code}: {error_content.decode()}'}}]})}\n\n"
                    return

                full_tool_call_json = ""
                tool_name = ""
                tool_call_id = ""
                has_tool_call = False

                async for line in response.aiter_lines():
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
                                    yield f"data: {json.dumps({'choices': [{'delta': {'content': f''}}]})}\n\n" # Frontend handles status update via side-channel if needed, but here we keep it clean
                            
                            if tc.get("function", {}).get("arguments"):
                                full_tool_call_json += tc["function"]["arguments"]
                            continue

                        if not has_tool_call:
                            yield f"{line}\n\n"
                            
                    except json.JSONDecodeError:
                        continue

                if has_tool_call:
                    # P2 Optimization: We can emit a specific "tool_processing" event here if frontend supports it
                    try:
                        args = json.loads(full_tool_call_json) if full_tool_call_json else {}
                        tool_result = await execute_tool(tool_name, args, user_id, config=config)
                        
                        # 构造继续对话的消息
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
                        
                        final_payload = {
                            "model": model,
                            "messages": messages,
                            "stream": True
                        }
                        async with client.stream("POST", chat_endpoint, headers=headers, json=final_payload) as final_resp:
                            async for final_line in final_resp.aiter_lines():
                                if final_line.startswith("data: "):
                                    yield f"{final_line}\n\n"
                    except Exception as e:
                         yield f"data: {json.dumps({'choices': [{'delta': {'content': f' AI 决策解析失败: {str(e)}'}}]})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'choices': [{'delta': {'content': f' Connection Error: {str(e)}'}}]})}\n\n"
    
    yield "data: [DONE]\n\n"


@router.post("/chat")
async def chat(request: ChatRequest):
    user_id = request.userId
    
    ai_config = {
        "base_url": "https://proxy.flydao.top/v1",
        "api_key": "",
        "model": "gpt-4o-mini"
    }

    if user_id:
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

    if request.agent == "@销售指挥官":
        system_prompt = prompts.SALES_COMMANDER
    elif request.agent == "@审批管家":
        system_prompt = prompts.APPROVAL_MANAGER
    elif request.agent == "@绩效教练":
        system_prompt = prompts.PERFORMANCE_COACH
    else:
        system_prompt = prompts.DEFAULT_FALLBACK
    
    formatted_messages = [{"role": "system", "content": system_prompt}]
    for msg in request.messages:
        formatted_messages.append({"role": msg.role, "content": msg.content})

    return StreamingResponse(
        stream_openai_response(formatted_messages, ai_config, user_id),
        media_type="text/event-stream"
    )

async def _error_stream(msg: str):
    yield f"data: {json.dumps({'choices': [{'delta': {'content': msg}}]})}\n\n"
    yield "data: [DONE]\n\n"
