from fastapi import APIRouter, Depends, status

from app.core.database import supabase
from app.core.dependencies import require_role
from app.core.errors import ErrorCode, api_error, api_success
from app.models.schemas import ProjectCreate, ProjectUpdate, StandardResponse

router = APIRouter(prefix="/api/projects", tags=["Projects"])


@router.get("/{user_id}", response_model=StandardResponse)
async def get_projects(user_id: str):
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
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/", response_model=StandardResponse, status_code=status.HTTP_201_CREATED)
async def create_project(project: ProjectCreate):
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
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.patch("/{project_id}", response_model=StandardResponse)
async def update_project(project_id: str, updates: ProjectUpdate):
    """
    Update an existing project.
    """
    try:
        # Filter out None values
        data = {k: v for k, v in updates.model_dump().items() if v is not None}

        if not data:
            return api_success(data=None, message="No updates provided")

        res = await supabase.table("projects").update(data).eq("id", project_id).execute()

        if not res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, f"Project {project_id} not found or update failed")

        return api_success(data=res.data[0], message="Project updated")
    except Exception as e:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


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
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
