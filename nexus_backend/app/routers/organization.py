"""
P2 Optimization: Organization Structure API Routes
Provides endpoints for managing organizational hierarchy and approval chains.
"""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.dependencies import require_role
from app.core.errors import ErrorCode, api_error, api_success
from app.models.schemas import StandardResponse
from app.services.approval_chain import approval_chain_service
from app.services.organization_service import organization_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/organization", tags=["Organization"])


@router.get("/detail")
async def get_organization_detail(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取当前所属组织的详情"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")
        org = await organization_service.get_organization(org_id=org_id, db=db)
        if not org:
            raise api_error(ErrorCode.NOT_FOUND, "组织不存在")
        return api_success(data=org)
    except Exception as e:
        logger.error(f"Failed to get organization detail: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取组织信息失败")


@router.put("/detail")
async def update_organization_detail(
    updates: dict,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新当前所属组织的详情"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")
        # 权限检查：只有 boss 和 founder 可以修改
        profile = (
            await db.table("users")
            .select("role")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        if not profile.data or profile.data.get("role") not in ["boss", "founder"]:
            raise api_error(ErrorCode.FORBIDDEN, "权限不足")

        # 过滤允许更新的字段
        allowed_fields = {"name", "invite_code_enabled"}
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        if not filtered_updates:
            raise api_error(ErrorCode.VALIDATION_MISSING_FIELD, "没有可更新的字段")

        result = await organization_service.update_organization(
            org_id=org_id, updates=filtered_updates, db=db
        )
        return api_success(data=result)
    except Exception as e:
        logger.error(f"Failed to update organization: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "更新组织信息失败")


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
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "Department not found")

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
async def get_organization_stats(
    req: Request, user_id: str = Depends(get_current_user_id)
):
    """
    Get organization-wide statistics.
    """
    org_id = getattr(req.state, "org_id", None)
    db = getattr(req.state, "db", None)

    if not org_id:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "Organization not found")

    stats = await organization_service.get_org_stats(org_id, db=db)
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
    except Exception:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "Approval level check failed")


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
    except Exception:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "Approval processing failed")


# ============== Organization Members Management ==============


@router.get("/members", response_model=StandardResponse)
async def get_organization_members(
    req: Request, user_id: str = Depends(get_current_user_id)
):
    """
    Get all members in the user's organization for the org chart management page.
    Returns: id, name, department, role, manager_id, avatar
    """
    client = req.state.db

    # Get the user's organization
    user_res = (
        await client.table("users")
        .select("organization_id")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    org_id = user_res.data.get("organization_id") if user_res.data else None

    if not org_id:
        raise api_error(
            ErrorCode.RESOURCE_NOT_FOUND, "Organization not found for current user"
        )

    # Fetch all members in the organization
    members_res = (
        await client.table("users")
        .select("id, name, department, role, manager_id, avatar")
        .eq("organization_id", org_id)
        .order("name")
        .execute()
    )

    members = []
    all_members = members_res.data or []

    # Build a name lookup for manager display
    name_map = {}
    for m in all_members:
        name_map[m["id"]] = m.get("name") or "未知"

    for m in all_members:
        members.append(
            {
                "id": m["id"],
                "full_name": m.get("name") or "未知",
                "department": m.get("department") or "",
                "role": m.get("role") or "employee",
                "manager_id": m.get("manager_id"),
                "manager_name": name_map.get(m.get("manager_id", "")),
                "avatar_url": m.get("avatar"),
            }
        )

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
    user_res = (
        await client.table("users")
        .select("organization_id, role")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )

    if not user_res.data:
        raise api_error(ErrorCode.AUTH_UNAUTHORIZED, "User not found")

    caller_role = user_res.data.get("role", "")
    if caller_role not in ("boss", "founder", "admin"):
        raise api_error(
            ErrorCode.AUTH_FORBIDDEN, "Only admins can update reporting relationships"
        )

    caller_org = user_res.data.get("organization_id")

    # Verify target user is in the same org
    target_res = (
        await client.table("users")
        .select("id, organization_id")
        .eq("id", target_user_id)
        .maybe_single()
        .execute()
    )

    if not target_res.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "Target user not found")

    if target_res.data.get("organization_id") != caller_org:
        raise api_error(
            ErrorCode.AUTH_FORBIDDEN, "Cannot modify users outside your organization"
        )

    # Prevent self-assignment as manager
    if body.manager_id == target_user_id:
        raise api_error(
            ErrorCode.VALIDATION_ERROR, "A user cannot be their own manager"
        )

    # If manager_id is provided, verify the manager exists in the same org
    if body.manager_id:
        manager_res = (
            await client.table("users")
            .select("id, organization_id")
            .eq("id", body.manager_id)
            .maybe_single()
            .execute()
        )

        if not manager_res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "Manager user not found")

        if manager_res.data.get("organization_id") != caller_org:
            raise api_error(
                ErrorCode.AUTH_FORBIDDEN, "Manager must be in the same organization"
            )

    # Update the manager_id (RLS policy "users_manager_update" allows boss/admin)
    update_res = (
        await client.table("users")
        .update({"manager_id": body.manager_id})
        .eq("id", target_user_id)
        .execute()
    )

    if not update_res.data:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "Failed to update manager")

    return api_success(
        data={"user_id": target_user_id, "manager_id": body.manager_id},
        message="Manager updated successfully",
    )


# ============== Invite Code Endpoints ==============


@router.post("/invite-code/regenerate", response_model=StandardResponse)
async def regenerate_invite_code(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """重新生成邀请码"""
    import secrets

    client = req.state.db

    # 获取用户的组织ID
    user_res = (
        await client.table("users")
        .select("organization_id")
        .eq("id", user_id)
        .single()
        .execute()
    )
    org_id = user_res.data.get("organization_id")

    if not org_id:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "Organization not found")

    # 生成新邀请码
    new_code = secrets.token_urlsafe(8)

    # 更新组织
    await client.table("organizations").update({"invite_code": new_code}).eq(
        "id", org_id
    ).execute()

    return api_success(data={"invite_code": new_code}, message="邀请码已重新生成")


@router.post("/invite-code/toggle", response_model=StandardResponse)
async def toggle_invite_code(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """切换邀请码启用状态"""
    client = req.state.db

    # 获取用户的组织ID
    user_res = (
        await client.table("users")
        .select("organization_id")
        .eq("id", user_id)
        .single()
        .execute()
    )
    org_id = user_res.data.get("organization_id")

    if not org_id:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "Organization not found")

    # 获取当前状态
    org_res = (
        await client.table("organizations")
        .select("invite_code_enabled")
        .eq("id", org_id)
        .single()
        .execute()
    )
    current = org_res.data.get("invite_code_enabled", True)

    # 切换状态
    new_status = not current
    await client.table("organizations").update({"invite_code_enabled": new_status}).eq(
        "id", org_id
    ).execute()

    return api_success(
        data={"enabled": new_status},
        message=f"邀请码已{'启用' if new_status else '禁用'}",
    )


# ============== Admin Endpoints ==============


async def _write_super_admin_audit(
    client,
    action: str,
    admin_user_id: str,
    organization_id: str | None,
    details: dict,
) -> None:
    try:
        await (
            client.table("audit_logs")
            .insert(
                {
                    "id": str(uuid.uuid4()),
                    "action": action,
                    "user_id": admin_user_id,
                    "organization_id": organization_id,
                    "details": details,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
            .execute()
        )
    except Exception as exc:
        logger.warning("Failed to write super admin audit log: %s", exc)


@router.get("/admin/pending-bosses", response_model=StandardResponse)
async def admin_list_pending_bosses(
    req: Request,
    user_id: str = Depends(require_role(["super_admin"])),
):
    """列出待审批的Boss申请"""
    from app.core.database import supabase

    # Admin 端点需要跨组织查询，使用 service-key client 绕过 RLS
    result = (
        await supabase.table("users")
        .select("id, name, email, created_at, organization_id")
        .eq("approval_status", "pending")
        .execute()
    )
    # 前端期望 user_id + organization_name 字段
    rows = []
    for u in result.data or []:
        org_name = ""
        if u.get("organization_id"):
            try:
                org_res = (
                    await supabase.table("organizations")
                    .select("name")
                    .eq("id", u["organization_id"])
                    .maybe_single()
                    .execute()
                )
                org_name = (org_res.data or {}).get("name", "")
            except Exception:
                pass
        rows.append(
            {
                "user_id": u["id"],
                "name": u.get("name", ""),
                "email": u.get("email", ""),
                "created_at": u.get("created_at", ""),
                "organization_name": org_name,
            }
        )
    return api_success(data=rows)


@router.get("/admin/organizations", response_model=StandardResponse)
async def admin_list_organizations(
    req: Request,
    user_id: str = Depends(require_role(["super_admin"])),
):
    """列出所有组织"""
    from app.core.database import supabase

    result = (
        await supabase.table("organizations")
        .select("id, name, slug, created_at")
        .execute()
    )
    # 前端期望 org_id + member_count 字段
    rows = []
    for org in result.data or []:
        try:
            cnt_res = (
                await supabase.table("users")
                .select("id", count="exact")
                .eq("organization_id", org["id"])
                .execute()
            )
            member_count = cnt_res.count or 0
        except Exception:
            member_count = 0
        rows.append(
            {
                "org_id": org["id"],
                "name": org.get("name", ""),
                "slug": org.get("slug", ""),
                "member_count": member_count,
                "created_at": org.get("created_at", ""),
            }
        )
    return api_success(data=rows)


@router.post("/admin/approve-boss/{target_user_id}", response_model=StandardResponse)
async def admin_approve_boss(
    target_user_id: str,
    req: Request,
    user_id: str = Depends(require_role(["super_admin"])),
):
    """批准Boss申请"""
    from app.core.database import supabase

    await supabase.table("users").update({"approval_status": "approved"}).eq(
        "id", target_user_id
    ).execute()
    await _write_super_admin_audit(
        supabase,
        "admin_approve_boss",
        user_id,
        None,
        {"target_user_id": target_user_id},
    )
    return api_success({}, message="已批准")


@router.post("/admin/reject-boss/{target_user_id}", response_model=StandardResponse)
async def admin_reject_boss(
    target_user_id: str,
    req: Request,
    user_id: str = Depends(require_role(["super_admin"])),
):
    """拒绝Boss申请"""
    from app.core.database import supabase

    await supabase.table("users").update(
        {"approval_status": "rejected", "role": "employee"}
    ).eq("id", target_user_id).execute()
    await _write_super_admin_audit(
        supabase,
        "admin_reject_boss",
        user_id,
        None,
        {"target_user_id": target_user_id},
    )
    return api_success({}, message="已拒绝")


@router.delete("/admin/organization/{org_id}", response_model=StandardResponse)
async def admin_delete_organization(
    org_id: str,
    req: Request,
    user_id: str = Depends(require_role(["super_admin"])),
):
    """删除组织"""
    from app.core.database import supabase

    await supabase.table("organizations").delete().eq("id", org_id).execute()
    await _write_super_admin_audit(
        supabase,
        "admin_delete_organization",
        user_id,
        org_id,
        {},
    )
    return api_success({}, message="组织已删除")


# ============== White-Label Branding Endpoints ==============


@router.get("/brand")
async def get_org_brand(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取组织白标品牌配置"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            return api_success(data={})
        db = getattr(req.state, "db", None)
        if not db:
            return api_success(data={})
        res = (
            await db.table("organizations")
            .select("brand")
            .eq("id", str(org_id))
            .maybe_single()
            .execute()
        )
        brand = (res.data or {}).get("brand", {}) or {}
        return api_success(data=brand)
    except Exception as e:
        logger.error(f"Failed to get org brand: {e}")
        return api_success(data={})


class BrandUpdateRequest(BaseModel):
    brand: dict


@router.put("/brand")
async def update_org_brand(
    body: BrandUpdateRequest,
    req: Request,
    user_id: str = Depends(require_role(["boss", "founder"])),
):
    """更新组织白标品牌配置（仅 boss/founder）"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")

        # Validate brand fields
        allowed_keys = {
            "logo_url",
            "primary_color",
            "company_name",
            "tagline",
            "login_title",
            "login_subtitle",
            "feature_cards",
            "favicon_url",
            "custom_domain",
        }
        brand = {k: v for k, v in body.brand.items() if k in allowed_keys}

        await db.table("organizations").update({"brand": brand}).eq(
            "id", str(org_id)
        ).execute()
        return api_success(data=brand, message="品牌配置已更新")
    except Exception as e:
        logger.error(f"Failed to update org brand: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "更新品牌配置失败")
