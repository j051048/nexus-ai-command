import asyncio
import json
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
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

# --- 工具定义 ---
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "approve_request",
            "description": "批准一个待处理的审批申请（报销或采购）",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "string", "description": "审批单的唯一ID"},
                    "reason": {"type": "string", "description": "批准的原因（可选）"}
                },
                "required": ["request_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reject_request",
            "description": "驳回一个待处理的审批申请",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "string", "description": "审批单的唯一ID"},
                    "reason": {"type": "string", "description": "驳回的原因（必须说明）"}
                },
                "required": ["request_id", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_approvals",
            "description": "获取当前所有待处理的异常审批列表",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_performance_report",
            "description": "获取指定用户的详细绩效报告",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "用户UUID，若为空则获取当前用户"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "award_badge",
            "description": "为员工颁发荣誉徽章或奖励",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "员工的唯一ID"},
                    "badge_name": {"type": "string", "description": "徽章名称，如：销售冠军、拼命三郎"},
                    "icon": {"type": "string", "description": "图标标识，如：trophy, rocket, fire"}
                },
                "required": ["user_id", "badge_name"]
            }
        }
    }
]

async def execute_tool(name: str, args: Dict[str, Any], current_user_id: str) -> str:
    """执行具体工具逻辑并返回结果文本"""
    try:
        if name == "approve_request":
            req_id = args.get("request_id")
            result = supabase.table("approval_requests").update({"status": "approved"}).eq("id", req_id).execute()
            if result.data:
                # 尝试创建通知
                try:
                    target_user = result.data[0].get("submitted_by")
                    supabase.table("notifications").insert({
                        "user_id": target_user,
                        "title": "审批已通过",
                        "content": f"您的审批申请 {req_id} 已被 AI 批准。",
                        "type": "success"
                    }).execute()
                except: pass
                return f"成功批准审批单 {req_id}。"
            return "批准失败，可能单据不存在或已由他人处理。"
            
        elif name == "reject_request":
            req_id = args.get("request_id")
            reason = args.get("reason", "未说明原因")
            result = supabase.table("approval_requests").update({"status": "rejected"}).eq("id", req_id).execute()
            if result.data:
                try:
                    target_user = result.data[0].get("submitted_by")
                    supabase.table("notifications").insert({
                        "user_id": target_user,
                        "title": "审批已驳回",
                        "content": f"您的审批申请 {req_id} 已被驳回。理由：{reason}",
                        "type": "error"
                    }).execute()
                except: pass
                return f"已成功驳回单据 {req_id}，理由：{reason}。"
            return "驳回失败。"

        elif name == "get_pending_approvals":
            result = supabase.table("approval_requests").select("*, users:submitted_by(name)").eq("status", "pending").execute()
            if not result.data:
                return "当前没有任何待处理的审批。"
            items = []
            for item in result.data:
                user_name = item.get("users", {}).get("name", "未知用户")
                items.append(f"ID: {item['id']}, 申请人: {user_name}, 类型: {item['type']}, 金额: ¥{item['amount']}, 描述: {item['description']}")
            return "待处理清单：\n" + "\n".join(items)

        elif name == "get_performance_report":
            target_id = args.get("user_id") or current_user_id
            user_res = supabase.table("users").select("*").eq("id", target_id).maybe_single().execute()
            if not user_res.data:
                return f"找不到 ID 为 {target_id} 的用户绩效数据。"
            
            user = user_res.data
            metrics_res = supabase.table("sales_metrics").select("*").eq("user_id", target_id).execute()
            leads_res = supabase.table("sales_leads").select("stage, count").eq("user_id", target_id).execute()
            # 这里的 count 是示意逻辑，实际根据 schema
            
            report = f"用户: {user['name']}\n"
            report += f"当前得分: {user['score']} | 排名: {user['rank']} | 总奖金: ¥{user['total_bonus']}\n"
            report += "关键指标:\n"
            for m in metrics_res.data:
                report += f"- {m['metric_type']}: {m['value']}\n"
            
            return report

        elif name == "award_badge":
            user_id = args.get("user_id")
            badge_name = args.get("badge_name")
            icon = args.get("icon", "sparkles")
            
            # 插入徽章
            supabase.table("badges").insert({
                "user_id": user_id,
                "name": badge_name,
                "icon": icon
            }).execute()
            
            # 创建通知
            supabase.table("notifications").insert({
                "user_id": user_id,
                "title": "荣获新徽章！",
                "content": f"老板为你颁发了「{badge_name}」徽章，继续加油！",
                "type": "success"
            }).execute()
            
            return f"成功为用户 {user_id} 颁发徽章: {badge_name}"
            
        return f"未知工具: {name}"
    except Exception as e:
        return f"执行工具时发生错误: {str(e)}"

async def stream_openai_response(messages: List[dict], config: dict, user_id: str):
    """
    Stream response from OpenAI with tool use support
    """
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    model = config.get("model")

    target_url = base_url
    if not target_url.endswith("/chat/completions"):
        if target_url.endswith("/"): target_url = target_url[:-1]
        if target_url.endswith("/v1"): target_url = f"{target_url}/chat/completions"
        else: target_url = f"{target_url}/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
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
            async with client.stream("POST", target_url, headers=headers, json=payload) as response:
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
                                    yield f"data: {json.dumps({'choices': [{'delta': {'content': f'⚡ AI 正在执行: {tool_name}...'}}]})}\n\n"
                            
                            if tc.get("function", {}).get("arguments"):
                                full_tool_call_json += tc["function"]["arguments"]
                            continue

                        if not has_tool_call:
                            yield f"{line}\n\n"
                            
                    except json.JSONDecodeError:
                        continue

                if has_tool_call:
                    content_str = json.dumps({'choices': [{'delta': {'content': '\n\n🛠️ 处理完成，正在生成总结...'}}]})
                    yield f"data: {content_str}\n\n"
                    
                    try:
                        args = json.loads(full_tool_call_json) if full_tool_call_json else {}
                        tool_result = await execute_tool(tool_name, args, user_id)
                        
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
                        async with client.stream("POST", target_url, headers=headers, json=final_payload) as final_resp:
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

    system_prompt = "You are Nexus AI, a helpful enterprise assistant. You can use tools to perform actions and query data."
    if request.agent == "@销售指挥官":
        system_prompt = "你是销售指挥官。你不仅能分析线索，还能调用绩效评估工具。你可以通过 get_performance_report 来查看员绩效。"
    elif request.agent == "@审批管家":
        system_prompt = "你是审批管家。你可以调用 get_pending_approvals 查看异常申请，并根据用户指令使用 approve_request 或 reject_request 进行实时操作。"
    elif request.agent == "@绩效教练":
        system_prompt = "你是绩效教练。通过 get_performance_report 分析数据并提供针对性建议。你要根据分数、排名和销售指标给出详细的激励方案。"
    
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


async def _error_stream(msg: str):
    yield f"data: {json.dumps({'choices': [{'delta': {'content': msg}}]})}\n\n"
    yield "data: [DONE]\n\n"
