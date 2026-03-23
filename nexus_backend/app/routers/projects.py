from fastapi import APIRouter, Depends, status

from app.core.auth import get_current_user_id
from app.core.database import supabase
from app.core.dependencies import require_role
from app.core.errors import ErrorCode, api_error, api_success
from app.models.schemas import ProjectCreate, ProjectUpdate, StandardResponse

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["Projects"])


@router.get("/", response_model=StandardResponse)
async def get_projects(user_id: str = Depends(get_current_user_id)):
    """
    Get projects for a user.
    Admin/Founder can see all projects (potentially), but standard behavior is RLS or owner check.
    """
    try:
        # Check user role for permission logic
        user_res = await supabase.table("users").select("role").eq("id", user_id).maybe_single().execute()
        role = user_res.data.get("role") if user_res.data else "employee"

        query = supabase.table("projects").select("*").neq("stage", "archived")

        # Security Policy: Non-founders only see their own projects
        if role not in ("founder", "boss"):
            query = query.eq("user_id", user_id)

        res = await query.order("created_at", desc=True).execute()

        return api_success(data=res.data)
    except Exception as e:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "项目操作失败")


@router.post("/", response_model=StandardResponse, status_code=status.HTTP_201_CREATED)
async def create_project(project: ProjectCreate, user_id: str = Depends(get_current_user_id)):
    """
    Create a new project.
    """
    try:
        data = {
            "name": project.name,
            "description": project.description,
            "user_id": project.userId,
            "stage": "planning",
            "progress": 0,
        }
        res = await supabase.table("projects").insert(data).execute()
        if not res.data:
            raise api_error(ErrorCode.DB_ERROR, "Project creation failed")

        return api_success(data=res.data[0], message="Project created successfully")
    except Exception as e:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "项目操作失败")


@router.patch("/{project_id}", response_model=StandardResponse)
async def update_project(project_id: str, updates: ProjectUpdate, user_id: str = Depends(get_current_user_id)):
    """
    Update an existing project.
    """
    try:
        # Filter out None values
        data = {k: v for k, v in updates.model_dump().items() if v is not None}

        # Map 'status' to DB column 'stage' (frontend sends status, DB uses stage)
        if "status" in data:
            data["stage"] = data.pop("status")

        if not data:
            return api_success(data=None, message="No updates provided")

        res = await supabase.table("projects").update(data).eq("id", project_id).execute()

        if not res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, f"Project {project_id} not found or update failed")

        return api_success(data=res.data[0], message="Project updated")
    except Exception as e:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "项目操作失败")


@router.delete("/{project_id}", response_model=StandardResponse)
async def delete_project(
    project_id: str,
    user_id: str = Depends(require_role(["admin", "founder", "boss"])),
):
    """删除项目（软删除 - 标记为 archived 状态）"""
    try:
        existing = await supabase.table("projects").select("id").eq("id", project_id).maybe_single().execute()
        if not existing.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "项目不存在")

        res = await supabase.table("projects").update({"stage": "archived"}).eq("id", project_id).execute()
        if not res.data:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "删除项目失败")

        return api_success(data=None, message="项目已删除")
    except Exception as e:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "项目操作失败")


@router.post("/{project_id}/weekly-report")
async def generate_weekly_report(
    project_id: str,
    user_id: str = Depends(require_role(["employee", "admin", "founder", "boss"])),
):
    """AI 生成项目周报 — 收集本周 timeline + 任务统计，调用 AI 生成四板块周报。"""
    from datetime import datetime, timedelta, timezone

    try:
        CN_TZ = timezone(timedelta(hours=8))
        now = datetime.now(CN_TZ)
        week_ago = (now - timedelta(days=7)).isoformat()

        # 1. 获取项目基本信息
        proj_res = await supabase.table("projects").select("*").eq("id", project_id).maybe_single().execute()
        if not proj_res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "项目不存在")
        project = proj_res.data

        # 2. 获取本周 timeline 事件
        timeline_res = await (
            supabase.table("project_timeline")
            .select("event_type, title, content, created_at")
            .eq("project_id", project_id)
            .gte("created_at", week_ago)
            .order("created_at", desc=True)
            .limit(30)
            .execute()
        )
        events = timeline_res.data or []

        # 3. 获取关联任务统计
        tasks_res = await (
            supabase.table("oa_tasks")
            .select("status, title")
            .contains("metadata", {"project_id": project_id})
            .execute()
        )
        tasks = tasks_res.data or []
        total_tasks = len(tasks)
        done_tasks = sum(1 for t in tasks if t.get("status") == "done")
        in_progress = sum(1 for t in tasks if t.get("status") == "in_progress")

        # 4. 构建 AI prompt
        event_lines = "\n".join(
            f"- [{e.get('created_at', '')[:10]}] [{e.get('event_type', '')}] {e.get('title', '')}: {(e.get('content') or '')[:100]}"
            for e in events
        ) or "本周无事件记录"

        prompt = f"""请为以下项目生成一份简洁的周报，包含四个板块：
1. 本周进展摘要
2. 关键里程碑与风险
3. 下周计划建议
4. 数据概览

项目信息：
- 名称：{project.get('name', '')}
- 描述：{project.get('description', '')[:200]}
- 当前阶段：{project.get('stage', '')}
- 进度：{project.get('progress', 0)}%

任务统计：总计 {total_tasks} 个任务，已完成 {done_tasks}，进行中 {in_progress}

本周事件：
{event_lines}

请用中文输出，格式清晰，每个板块用标题分隔。"""

        # 5. 调用 AI 生成
        from app.services.llm_helpers import resolve_model_config, get_langchain_llm_sync

        config = await resolve_model_config(
            scene_code="content_generation",
            complexity_tier="balanced",
        )
        llm = get_langchain_llm_sync(
            api_key=config["api_key"],
            base_url=config["base_url"],
            model=config["model"],
            temperature=0.7,
            timeout=config.get("timeout", 60.0),
        )

        result = await llm.ainvoke(prompt)
        report_text = result.content if hasattr(result, "content") else str(result)

        # 6. 写入 timeline 作为记录
        await supabase.table("project_timeline").insert({
            "project_id": project_id,
            "event_type": "ai_report",
            "title": f"AI 周报 ({now.strftime('%m/%d')})",
            "content": report_text[:2000],
            "user_id": user_id,
        }).execute()

        return api_success(
            data={
                "report": report_text,
                "stats": {
                    "total_tasks": total_tasks,
                    "done_tasks": done_tasks,
                    "in_progress": in_progress,
                    "events_count": len(events),
                },
            },
            message="周报生成成功",
        )
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error("Generate weekly report error: %s", e)
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "项目操作失败")
