import asyncio
import json
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from app.core.database import supabase

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

async def stream_openai_response(messages: List[dict], config: dict):
    """
    Stream response from OpenAI-compatible API
    """
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    model = config.get("model")

    # Normalize Base URL
    if not base_url.endswith("/v1") and not base_url.endswith("/chat/completions"):
        if "flydao" in base_url: # Auto fix for known proxy common patterns if needed, but standardizing on /v1 is safer
             pass 

    # We need to construct the full URL for the chat completions endpoint
    # If base_url ends with /chat/completions, use it directly.
    # Otherwise, try to append /chat/completions coming from a standard base.
    
    target_url = base_url
    if not target_url.endswith("/chat/completions"):
        if target_url.endswith("/"):
            target_url = target_url[:-1]
        
        if target_url.endswith("/v1"):
            target_url = f"{target_url}/chat/completions"
        else:
            target_url = f"{target_url}/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.7
    }

    # print(f"Connecting to AI Provider: {target_url} with model {model}")

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            async with client.stream("POST", target_url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    error_content = await response.aread()
                    yield f"data: {json.dumps({'choices': [{'delta': {'content': f' Error {response.status_code}: {error_content.decode()}'}}]})}\n\n"
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        yield f"{line}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'choices': [{'delta': {'content': f' Connection Error: {str(e)}'}}]})}\n\n"
    
    yield "data: [DONE]\n\n"


@router.post("/chat")
async def chat(request: ChatRequest):
    # 1. Get User Settings from DB
    user_id = request.userId
    
    # Default Config (Fallback)
    ai_config = {
        "base_url": "https://proxy.flydao.top/v1",
        "api_key": "", # User must provide this ideally, but if they put it in DB we use it
        "model": "gpt-3.5-turbo"
    }

    if user_id:
        try:
            # Fetch settings from 'ai_settings' table
            response = supabase.table("ai_settings").select("*").eq("user_id", user_id).maybe_single().execute()
            if response.data:
                settings = response.data
                ai_config["base_url"] = settings.get("base_url") or ai_config["base_url"]
                ai_config["api_key"] = settings.get("api_key") or ""
                ai_config["model"] = settings.get("model") or ai_config["model"]
        except Exception as e:
            print(f"Failed to fetch user settings: {e}")

    # Validate API Key
    if not ai_config["api_key"]:
        # Allow free testing if strictly using the known proxy loop? No, usually proxy needs key.
        # But maybe user hardcoded key in env? 
        # For now, if no key, warn user.
        return StreamingResponse(
            _error_stream("请先在系统设置中配置您的 API Key"), 
            media_type="text/event-stream"
        )

    # 2. Format Messages for OpenAI
    # Convert Pydantic models to pure dicts
    formatted_messages = []
    # Add System Prompt based on Agent
    system_prompt = "You are Nexus AI, a helpful enterprise assistant."
    if request.agent == "@销售指挥官":
        system_prompt = "你是销售指挥官，专注于分析销售线索、提供跟进策略和话术建议。回答要专业、简练，以销售转化率为核心目标。"
    elif request.agent == "@审批管家":
        system_prompt = "你是审批管家，负责检查报销单和采购申请。关注预算合规性、异常金额和潜在风险。"
    elif request.agent == "@绩效教练":
        system_prompt = "你是绩效教练，负责激励员工，分析绩效数据，提供提升建议。语气要在严格中带有鼓励。"
    
    formatted_messages.append({"role": "system", "content": system_prompt})

    for msg in request.messages:
        formatted_messages.append({
            "role": msg.role,
            "content": msg.content
        })

    # 3. Stream Response
    return StreamingResponse(
        stream_openai_response(formatted_messages, ai_config),
        media_type="text/event-stream"
    )

async def _error_stream(msg: str):
    yield f"data: {json.dumps({'choices': [{'delta': {'content': msg}}]})}\n\n"
    yield "data: [DONE]\n\n"
