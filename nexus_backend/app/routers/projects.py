from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from app.core.database import supabase

router = APIRouter(prefix="/api/projects", tags=["Projects"])

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    userId: str # owner_id

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[int] = None

@router.get("/{user_id}")
async def get_projects(user_id: str):
    # If user is boss, logic might differ (fetch all), but for now we follow RLS/or query param
    # Front-end for Employee passes their own ID.
    try:
        # Check role to decide if we fetch all or just user's
        # BUT supabase-py RLS might not work if we use service_role key globally?
        # The app.core.database usually uses a service_role key for admin tasks.
        # So we should manually filter unless we have per-request user context client.
        # Implementation: Check user role.
        user_res = supabase.table("users").select("role").eq("id", user_id).maybe_single().execute()
        role = user_res.data.get("role") if user_res.data else "employee"
        
        query = supabase.table("projects").select("*")
        
        if role != 'founder':
            query = query.eq("owner_id", user_id)
            
        res = query.order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/")
async def create_project(project: ProjectCreate):
    try:
        data = {
            "name": project.name,
            "description": project.description,
            "owner_id": project.userId,
            "status": "planning",
            "progress": 0
        }
        res = supabase.table("projects").insert(data).execute()
        if not res.data:
            raise Exception("Insert failed")
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{project_id}")
async def update_project(project_id: str, updates: ProjectUpdate):
    try:
        data = {k: v for k, v in updates.model_dump().items() if v is not None}
        res = supabase.table("projects").update(data).eq("id", project_id).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
