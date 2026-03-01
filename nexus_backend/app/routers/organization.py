"""
P2 Optimization: Organization Structure API Routes
Provides endpoints for managing organizational hierarchy and approval chains.
"""


from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.models.schemas import StandardResponse
from app.services.approval_chain import approval_chain_service
from app.services.organization import organization_service

router = APIRouter(prefix="/api/organization", tags=["Organization"])


@router.get("/departments", response_model=StandardResponse)
async def get_departments(user_id: str = Depends(get_current_user_id)):
    """
    Get all departments in the organization.
    """
    departments = await organization_service.get_all_departments()
    # P1 Fix #12: Filter by user's org if needed, though get_all_departments
    # should eventually also take org_id. For now RLS handles it.
    return api_success(data=departments)


@router.get("/departments/{department_id}", response_model=StandardResponse)
async def get_department(department_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Get a specific department by ID.
    """
    department = await organization_service.get_department(department_id)
    if not department:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "Department not found")

    return api_success(data=department)


@router.get("/departments/{department_id}/members", response_model=StandardResponse)
async def get_department_members(department_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Get all members of a specific department.
    """
    members = await organization_service.get_department_members(department_id)
    return api_success(data=members, message=f"Found {len(members)} members")


@router.get("/tree", response_model=StandardResponse)
async def get_organization_tree(user_id: str = Depends(get_current_user_id)):
    """
    Get the full organization tree hierarchy.
    """
    tree = await organization_service.get_department_tree()
    return api_success(data=[node.to_dict() for node in tree])


@router.get("/stats", response_model=StandardResponse)
async def get_organization_stats(user_id: str = Depends(get_current_user_id)):
    """
    Get organization-wide statistics.
    """
    # P1 Fix #15: Pass org_id to stats
    # Simple way to get org_id (fetch from users table)
    from app.core.database import supabase

    user_res = await supabase.table("users").select("org_id").eq("id", user_id).maybe_single().execute()
    org_id = user_res.data.get("org_id") if user_res.data else None

    if not org_id:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "Organization not found")

    stats = await organization_service.get_org_stats(org_id)
    if "error" in stats:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, stats["error"])
    return api_success(data=stats)


@router.get("/users/{target_user_id}/reporting-line", response_model=StandardResponse)
async def get_user_reporting_line(target_user_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Get the reporting line (chain of managers) for a user.
    """
    reporting_line = await organization_service.get_user_reporting_line(target_user_id)
    return api_success(data=reporting_line)


@router.get("/users/{manager_id}/direct-reports", response_model=StandardResponse)
async def get_direct_reports(manager_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Get all users who directly report to a manager.
    """
    reports = await organization_service.get_direct_reports(manager_id)
    return api_success(data=reports)


@router.get("/users/{manager_id}/team", response_model=StandardResponse)
async def get_team_hierarchy(manager_id: str, max_depth: int = 3, user_id: str = Depends(get_current_user_id)):
    """
    Get the full team hierarchy under a manager.
    """
    team = await organization_service.get_team_hierarchy(manager_id, max_depth)
    return api_success(data=team.to_dict() if team else None)


# ============== Approval Chain Endpoints ==============


@router.get("/approval-chains", response_model=StandardResponse)
async def get_approval_chains(user_id: str = Depends(get_current_user_id)):
    """
    Get all configured approval chains.
    """
    chains = approval_chain_service.get_all_chains()
    return api_success(data=chains)


@router.get("/approval-chains/{approval_type}/level", response_model=StandardResponse)
async def get_approval_level(approval_type: str, amount: float, user_id: str = Depends(get_current_user_id)):
    """
    Determine the approval level required for a given type and amount.
    """
    try:
        step, step_index = approval_chain_service.determine_approval_level(approval_type, amount)

        return api_success(
            data={
                "step_index": step_index,
                "level": step.level.value,
                "threshold": step.threshold,
                "approver_role": step.approver_role,
                "timeout_hours": step.timeout_hours,
            }
        )
    except Exception as e:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, f"Approval level check failed: {str(e)}")


@router.post("/approval-chains/process", response_model=StandardResponse)
async def process_approval_through_chain(
    request_id: str,
    approval_type: str,
    amount: float,
    description: str = "",
    user_id: str = Depends(get_current_user_id),
):
    """
    Process a new approval request through the approval chain.
    """
    try:
        result = await approval_chain_service.process_approval_request(
            request_id=request_id,
            approval_type=approval_type,
            amount=amount,
            requester_id=user_id,
            description=description,
        )
        return api_success(data=result, message="Approval Request Processed")
    except Exception as e:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, f"Approval processing failed: {str(e)}")


# ============== Organization Members Management ==============


@router.get("/members", response_model=StandardResponse)
async def get_organization_members(req: Request, user_id: str = Depends(get_current_user_id)):
    """
    Get all members in the user's organization for the org chart management page.
    Returns: id, name, department, role, manager_id, avatar
    """
    client = req.state.db

    # Get the user's organization
    user_res = await client.table("users").select("organization_id").eq("id", user_id).maybe_single().execute()
    org_id = user_res.data.get("organization_id") if user_res.data else None

    if not org_id:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "Organization not found for current user")

    # Fetch all members in the organization
    members_res = await client.table("users").select(
        "id, name, department, role, manager_id, avatar"
    ).eq("organization_id", org_id).order("name").execute()

    members = []
    all_members = members_res.data or []

    # Build a name lookup for manager display
    name_map = {}
    for m in all_members:
        name_map[m["id"]] = m.get("name") or "未知"

    for m in all_members:
        members.append({
            "id": m["id"],
            "full_name": m.get("name") or "未知",
            "department": m.get("department") or "",
            "role": m.get("role") or "employee",
            "manager_id": m.get("manager_id"),
            "manager_name": name_map.get(m.get("manager_id", "")),
            "avatar_url": m.get("avatar"),
        })

    return api_success(data=members, message=f"Found {len(members)} members")


class UpdateManagerRequest(BaseModel):
    manager_id: str | None = None


@router.put("/members/{target_user_id}/manager", response_model=StandardResponse)
async def update_user_manager(
    target_user_id: str,
    body: UpdateManagerRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Update the manager_id for a user (org chart management).
    Only admins/bosses should call this (enforced via frontend role guard).
    """
    client = req.state.db

    # Verify the requesting user is in the same org and has boss/admin role
    user_res = await client.table("users").select(
        "organization_id, role"
    ).eq("id", user_id).maybe_single().execute()

    if not user_res.data:
        raise api_error(ErrorCode.AUTH_UNAUTHORIZED, "User not found")

    caller_role = user_res.data.get("role", "")
    if caller_role not in ("boss", "founder", "admin"):
        raise api_error(ErrorCode.AUTH_FORBIDDEN, "Only admins can update reporting relationships")

    caller_org = user_res.data.get("organization_id")

    # Verify target user is in the same org
    target_res = await client.table("users").select(
        "id, organization_id"
    ).eq("id", target_user_id).maybe_single().execute()

    if not target_res.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "Target user not found")

    if target_res.data.get("organization_id") != caller_org:
        raise api_error(ErrorCode.AUTH_FORBIDDEN, "Cannot modify users outside your organization")

    # Prevent self-assignment as manager
    if body.manager_id == target_user_id:
        raise api_error(ErrorCode.VALIDATION_ERROR, "A user cannot be their own manager")

    # If manager_id is provided, verify the manager exists in the same org
    if body.manager_id:
        manager_res = await client.table("users").select(
            "id, organization_id"
        ).eq("id", body.manager_id).maybe_single().execute()

        if not manager_res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "Manager user not found")

        if manager_res.data.get("organization_id") != caller_org:
            raise api_error(ErrorCode.AUTH_FORBIDDEN, "Manager must be in the same organization")

    # Update the manager_id
    update_res = await client.table("users").update(
        {"manager_id": body.manager_id}
    ).eq("id", target_user_id).execute()

    if not update_res.data:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "Failed to update manager")

    return api_success(data={"user_id": target_user_id, "manager_id": body.manager_id}, message="Manager updated successfully")
