from .base_tool import BaseTool
from typing import Dict, Any
from app.core.database import supabase


def _get_client(config: Dict = None):
    """Get scoped DB client if user token available, else fallback to service client."""
    token = config.get("token") if config else None
    return supabase.get_scoped_client(token) if token and supabase else supabase

class ProjectListTool(BaseTool):
    name = "get_projects"
    description = "获取当前所有进行中的项目列表，用于关联后续的事件记录"

    parameters = {
        "type": "object",
        "properties": {}
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        client = _get_client(config)
        # Check role to filter projects? For now, list all accessible via RLS
        result = await client.table("projects").select("id, name, status, progress").execute()
        if not result.data:
            return "暂无进行中的项目。"
        items = [f"ID: {p['id']} | 名称: {p['name']} | 状态: {p['status']} | 进度: {p['progress']}%" for p in result.data]
        return "项目清单：\n" + "\n".join(items)

class CreateProjectTool(BaseTool):
    name = "create_project"
    description = "创建一个新的项目立项。当用户说'帮我新建一个XXX项目'时使用此工具。"
    
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "项目名称"},
            "description": {"type": "string", "description": "项目背景描述"},
            "status": {"type": "string", "description": "初始状态 (planning, in_progress)", "default": "planning"}
        },
        "required": ["name"]
    }
    
    required_role = "all"

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        name = args.get("name")
        description = args.get("description", "")
        status = args.get("status", "planning")
        
        try:
            data = {
                "name": name,
                "description": description,
                "owner_id": user_id,
                "status": status,
                "progress": 0
            }
            client = _get_client(config)
            res = await client.table("projects").insert(data).execute()
            if res.data:
                pid = res.data[0]['id']
                return f"✅ 项目 '{name}' 已成功立项 (ID: {pid})！您可以继续添加项目事件或里程碑。"
            return "创建失败。"
        except Exception as e:
            return f"系统错误: {str(e)}"

class CreateEventTool(BaseTool):
    name = "create_project_event"
    description = "在指定的项目中创建一个新的进度事件或关键节点（如：请客吃饭、技术突破、签署合同）"

    parameters = {
        "type": "object",
        "properties": {
            "project_id": {"type": "string", "description": "项目UUID (可先调用 get_projects 获取)"},
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
        
        # Ensure project_timeline table exists (it might be missing in migration, so we should allow fallback or catch error)
        # Assuming table exists or we need to add it to migration.
        # Check migration: I only added `projects` table. I did NOT add `project_timeline`.
        # I MUST add project_timeline table.
        try:
            client = _get_client(config)
            result = await client.table("project_timeline").insert({
                "project_id": project_id,
                "title": title,
                "content": content,
                "event_type": event_type,
                "created_by": user_id
            }).execute()
            
            if result.data:
                return f"成功在项目中创建了事件: {title}。"
        except Exception as e:
            return f"创建事件失败: {str(e)}"
        return "创建失败，请核对项目 ID 是否正确。"
