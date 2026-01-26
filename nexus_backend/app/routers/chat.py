from app.services.vector_service import vector_service
import json
import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.core.database import supabase
from app.core.prompts import prompts

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
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_stats",
            "description": "获取公司整体统计数据，如员工总人数、部门分布概况等",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_knowledge_base",
            "description": "查询企业知识库/向量数据库，获取公司政策、业务流程、文档等非结构化数据环境数据",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词或问题"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_projects",
            "description": "获取当前所有进行中的项目列表，用于关联后续的事件记录",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_project_event",
            "description": "在指定的项目中创建一个新的进度事件或关键节点（如：请客吃饭、技术突破、签署合同）",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目UUID"},
                    "title": {"type": "string", "description": "事件标题，如：庆功晚宴"},
                    "content": {"type": "string", "description": "事件详细描述，包括地点、参与人等"},
                    "event_type": {"type": "string", "enum": ["milestone", "meeting", "dinner", "task"], "description": "事件类型"}
                },
                "required": ["project_id", "title", "content", "event_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_tender_document",
            "description": "【智能投标专家】分析招标文件（文本），提取*号否决性条款并与公司产品对比，生成合规性矩阵",
            "parameters": {
                "type": "object",
                "properties": {
                    "tender_text": {"type": "string", "description": "招标文件的关键参数段落文本"}
                },
                "required": ["tender_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_battlecard",
            "description": "【销售赋能】获取竞争对手的打击卡（Battlecard），包含我方优势、对方弱点及反击话术",
            "parameters": {
                "type": "object",
                "properties": {
                    "competitor_name": {"type": "string", "description": "竞争对手名称，如：安捷伦, 赛默飞, 岛津"}
                },
                "required": ["competitor_name"]
            }
        }
    }
]

async def execute_tool(name: str, args: Dict[str, Any], current_user_id: str, config: dict = None) -> str:
    """执行具体工具逻辑并返回结果文本"""
    try:
        if name == "approve_request":
            req_id = args.get("request_id")
            result = supabase.table("approval_requests").update({"status": "approved"}).eq("id", req_id).execute()
            if result.data:
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
            supabase.table("badges").insert({"user_id": user_id, "name": badge_name, "icon": icon}).execute()
            supabase.table("notifications").insert({
                "user_id": user_id,
                "title": "荣获新徽章！",
                "content": f"老板为你颁发了「{badge_name}」徽章，继续加油！",
                "type": "success"
            }).execute()
            return f"成功为用户 {user_id} 颁发徽章: {badge_name}"

        elif name == "get_company_stats":
            count_res = supabase.table("users").select("id", count="exact").execute()
            total_users = count_res.count if count_res.count is not None else 0
            dept_res = supabase.table("users").select("department").execute()
            depts = {}
            for u in dept_res.data:
                d = u.get("department", "未分配") or "未分配"
                depts[d] = depts.get(d, 0) + 1
            stats = f"公司总人数: {total_users} 人\n分布:\n"
            for d, c in depts.items(): stats += f"- {d}: {c} 人\n"
            return stats

        elif name == "query_knowledge_base":
            query = args.get("query")
            return await vector_service.search(query, config=config)

        elif name == "get_projects":
            result = supabase.table("projects").select("id, name, stage").execute()
            if not result.data:
                return "暂无进行中的项目。"
            items = [f"ID: {p['id']} | 名称: {p['name']} | 阶段: {p['stage']}" for p in result.data]
            return "项目清单：\n" + "\n".join(items)

        elif name == "create_project_event":
            project_id = args.get("project_id")
            title = args.get("title")
            content = args.get("content")
            event_type = args.get("event_type")
            
            result = supabase.table("project_timeline").insert({
                "project_id": project_id,
                "title": title,
                "content": content,
                "event_type": event_type
            }).execute()
            
            if result.data:
                return f"成功在项目中创建了事件: {title}。"
            return "创建失败，请核对项目 ID 是否正确。"

        elif name == "analyze_tender_document":
            text = args.get("tender_text", "")
            # Logic: Split by lines, find "*", compare
            lines = text.split("\n")
            matrix = []
            for line in lines:
                if "*" in line or "必须" in line:
                    status = "✅ 满足" if "0.5%" in line or "15分钟" in line else "⚠️ 需确认 (偏离风险)"
                    matrix.append(f"- 条款: {line.strip()}\n  结果: {status}")
            
            return "📋 智能合规性矩阵 (Compliance Matrix):\n" + "\n".join(matrix) if matrix else "文本中未检测到明显的否决性条款 (*号条款)。"

        elif name == "get_battlecard":
            comp = args.get("competitor_name", "").lower()
            # Mock Data for Battlecards - in production this comes from DB
            cards = {
                "安捷伦": {
                    "weakness": "价格普遍高出 30%，售后响应周期长（平均 48h）",
                    "strength": "我方 ZY-100 性价比高，且只需 2 小时上门",
                    "tactic": "强调'全生命周期成本(TCO)'，展示我们的 5 年保修政策"
                },
                "赛默飞": {
                    "weakness": "软件操作复杂，对新手不友好，培训成本高",
                    "strength": "我方 One-Click 傻瓜式操作，30分钟上手",
                    "tactic": "现场演示软件操作流程，对比点击次数"
                }
            }
            
            data = None
            for k, v in cards.items():
                if k in comp or comp in k:
                    data = v
                    break
            
            if data:
                return f"⚔️ 竞品打击卡 (vs {comp}):\n- 对方弱点: {data['weakness']}\n- 我方优势: {data['strength']}\n- 建议话术: {data['tactic']}"
            return f"暂无关于 {comp} 的详细打击卡数据，建议查阅知识库通用话术。"
            
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
                                    # yield f"data: {json.dumps({'choices': [{'delta': {'content': f'⚡ AI 正在执行: {tool_name}...'}}]})}\n\n"
                            
                            if tc.get("function", {}).get("arguments"):
                                full_tool_call_json += tc["function"]["arguments"]
                            continue

                        if not has_tool_call:
                            yield f"{line}\n\n"
                            
                    except json.JSONDecodeError:
                        continue

                if has_tool_call:
                    # yield f"data: {json.dumps({'choices': [{'delta': {'content': '\n\n🛠️ 处理完成，正在生成总结...'}}]})}\n\n"
                    
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
