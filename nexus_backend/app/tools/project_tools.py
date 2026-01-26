from .base_tool import BaseTool
from typing import Dict, Any
from app.core.database import supabase

class ProjectListTool(BaseTool):
    name = "get_projects"
    description = "获取当前所有进行中的项目列表，用于关联后续的事件记录"

    parameters = {
        "type": "object",
        "properties": {}
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        result = supabase.table("projects").select("id, name, stage").execute()
        if not result.data:
            return "暂无进行中的项目。"
        items = [f"ID: {p['id']} | 名称: {p['name']} | 阶段: {p['stage']}" for p in result.data]
        return "项目清单：\n" + "\n".join(items)

class CreateEventTool(BaseTool):
    name = "create_project_event"
    description = "在指定的项目中创建一个新的进度事件或关键节点（如：请客吃饭、技术突破、签署合同）"

    parameters = {
        "type": "object",
        "properties": {
            "project_id": {"type": "string", "description": "项目UUID"},
            "title": {"type": "string", "description": "事件标题，如：庆功晚宴"},
            "content": {"type": "string", "description": "事件详细描述，包括地点、参与人等"},
            "event_type": {"type": "string", "enum": ["milestone", "meeting", "dinner", "task"], "description": "事件类型"}
        },
        "required": ["project_id", "title", "content", "event_type"]
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
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
