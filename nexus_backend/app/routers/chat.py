from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import json

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

async def fake_ai_generator(message: str, agent: str):
    """
    Simulate AI typing for demo purposes.
    In a real scenario, this would call an LLM (OpenAI/Anthropic) using LangChain or SDK.
    """
    intro = f"正在为您连接 {agent or 'Nexus智能中枢'}...\n"
    response_text = f"我已收到您的指令：「{message}」。\n\n这是来自 Zeabur Python 后端的实时响应。目前我的大脑（LLM）尚未完全连接，但我已准备好为您服务！🚀"
    
    full_text = intro + response_text

    # Simulate thinking/network latency
    await asyncio.sleep(0.5)
    
    for char in full_text:
        # Simulate typing speed
        await asyncio.sleep(0.02)
        
        # Format as OpenAI-compatible SSE stream
        chunk = {
            "choices": [
                {
                    "delta": {
                        "content": char
                    }
                }
            ]
        }
        yield f"data: {json.dumps(chunk)}\n\n"
    
    yield "data: [DONE]\n\n"

@router.post("/chat")
async def chat(request: ChatRequest):
    last_user_msg = request.messages[-1].content if request.messages else ""
    return StreamingResponse(
        fake_ai_generator(last_user_msg, request.agent),
        media_type="text/event-stream"
    )
