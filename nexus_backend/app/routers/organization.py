"""
P2 Optimization: Organization Structure API Routes
Provides endpoints for managing organizational hierarchy and approval chains.
"""

from fastapi import APIRouter, Depends
from app.core.auth import get_current_user_id
from app.services.organization import organization_service
from app.services.approval_chain import approval_chain_service
from app.models.schemas import StandardResponse
from app.core.errors import api_success, api_error, ErrorCode

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
async def get_department(
    department_id: str, user_id: str = Depends(get_current_user_id)
):
    """
    Get a specific department by ID.
    """
    department = await organization_service.get_department(department_id)
    if not department:
        raise api_error(ErrorCode.NOT_FOUND, "Department not found")

    return api_success(data=department)


@router.get("/departments/{department_id}/members", response_model=StandardResponse)
async def get_department_members(
    department_id: str, user_id: str = Depends(get_current_user_id)
):
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

    user_res = (
        await supabase.table("users")
        .select("org_id")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    org_id = user_res.data.get("org_id") if user_res.data else None

    if not org_id:
        raise api_error(ErrorCode.NOT_FOUND, "Organization not found")

    stats = await organization_service.get_org_stats(org_id)
    if "error" in stats:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, stats["error"])
    return api_success(data=stats)


@router.get("/users/{target_user_id}/reporting-line", response_model=StandardResponse)
async def get_user_reporting_line(
    target_user_id: str, user_id: str = Depends(get_current_user_id)
):
    """
    Get the reporting line (chain of managers) for a user.
    """
    reporting_line = await organization_service.get_user_reporting_line(target_user_id)
    return api_success(data=reporting_line)


@router.get("/users/{manager_id}/direct-reports", response_model=StandardResponse)
async def get_direct_reports(
    manager_id: str, user_id: str = Depends(get_current_user_id)
):
    """
    Get all users who directly report to a manager.
    """
    reports = await organization_service.get_direct_reports(manager_id)
    return api_success(data=reports)


@router.get("/users/{manager_id}/team", response_model=StandardResponse)
async def get_team_hierarchy(
    manager_id: str, max_depth: int = 3, user_id: str = Depends(get_current_user_id)
):
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
async def get_approval_level(
    approval_type: str, amount: float, user_id: str = Depends(get_current_user_id)
):
    """
    Determine the approval level required for a given type and amount.
    """
    try:
        step, step_index = approval_chain_service.determine_approval_level(
            approval_type, amount
        )

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
        raise api_error(
            ErrorCode.SYSTEM_INTERNAL_ERROR, f"Approval level check failed: {str(e)}"
        )


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
        raise api_error(
            ErrorCode.SYSTEM_INTERNAL_ERROR, f"Approval processing failed: {str(e)}"
        )
