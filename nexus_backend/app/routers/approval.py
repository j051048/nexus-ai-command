import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.models.schemas import ApprovalRequest, StandardResponse
from app.services.approval_chain import approval_chain_service
from app.services.approval_service import ApprovalService
from app.services.form_schema_service import form_schema_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/approval", tags=["Approval"])


# ============== Request Models ==============


class SubmitWithFormRequest(BaseModel):
    type: str  # 审批类型
    amount: float = Field(default=0.0, ge=0)
    details: str
    form_data: dict[str, Any] = {}

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v):
        if v is None or v == "": return 0.0
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0


class AdvanceDecisionRequest(BaseModel):
    """推进审批链的请求体"""

    decision: str = Field(..., pattern="^(approved|rejected)$", description="审批决定: approved 或 rejected")
    comment: str | None = Field(None, description="审批备注（可选）")


class SmartSubmitRequest(BaseModel):
    """智能提交审批请求 - 自动匹配工作流链"""

    type: str = Field(..., description="审批类型")
    amount: float = Field(default=0.0, ge=0, description="金额")
    description: str = Field(..., min_length=1, description="申请说明")
    form_data: dict[str, Any] = Field(default_factory=dict, description="表单数据")
    
    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v):
        if v is None or v == "": return 0.0
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0


# ============== Endpoints ==============


# ---- 统一审批门户端点 (必须在 /{request_id} 路由之前) ----


@router.get("/type-config")
async def get_approval_type_config(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取当前组织的审批类型配置列表。首次访问自动 seed 默认类型。"""
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "需要组织上下文")

    client = getattr(request.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    try:
        result = (
            await client.table("approval_type_config")
            .select("*")
            .eq("organization_id", org_id)
            .eq("is_active", True)
            .order("sort_order")
            .execute()
        )

        # 首次访问无数据 → 自动 seed
        if not result.data:
            await client.rpc("seed_default_approval_types", {"p_org_id": org_id}).execute()
            result = (
                await client.table("approval_type_config")
                .select("*")
                .eq("organization_id", org_id)
                .eq("is_active", True)
                .order("sort_order")
                .execute()
            )

        return api_success(data=result.data or [], message="审批类型配置获取成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get approval type config error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/list")
async def list_approvals(
    request: Request,
    tab: str = Query("pending", pattern="^(pending|mine|handled)$"),
    type_filter: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
):
    """
    统一审批列表查询。

    三个标签页:
    - pending: 待我处理的审批
    - mine: 我发起的审批
    - handled: 我已处理的审批

    同时查询 approval_requests + oa_leave_requests 两张表，归一化返回。
    """
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "需要组织上下文")

    client = getattr(request.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    try:
        items = []

        # --- 1. 查 approval_requests ---
        if not type_filter or type_filter != "leave":
            ar_query = (
                client.table("approval_requests")
                .select(
                    "id, type, description, amount, status, submitted_by, created_at, "
                    "approval_history, approval_level, users:submitted_by(name)"
                )
                .eq("organization_id", org_id)
            )

            if type_filter:
                ar_query = ar_query.eq("type", type_filter)

            if tab == "pending":
                ar_query = ar_query.eq("status", "pending").neq("submitted_by", user_id)
            elif tab == "mine":
                ar_query = ar_query.eq("submitted_by", user_id)
            elif tab == "handled":
                ar_query = ar_query.neq("status", "pending")

            ar_query = ar_query.order("created_at", desc=True).limit(200)
            ar_result = await ar_query.execute()

            for item in ar_result.data or []:
                # handled 标签页：过滤只包含当前用户处理过的
                if tab == "handled":
                    history = item.get("approval_history") or []
                    if not any(h.get("approver_id") == user_id for h in history):
                        continue

                submitter = item.get("users")
                items.append(
                    {
                        "id": item["id"],
                        "source_table": "approval_requests",
                        "type": item.get("type", ""),
                        "description": item.get("description", ""),
                        "amount": item.get("amount"),
                        "status": item.get("status", ""),
                        "submitted_by": item.get("submitted_by", ""),
                        "submitter_name": submitter.get("name") if isinstance(submitter, dict) else None,
                        "created_at": item.get("created_at", ""),
                    }
                )

        # --- 2. 查 oa_leave_requests ---
        if not type_filter or type_filter == "leave":
            lr_query = client.table("oa_leave_requests").select(
                "id, type, reason, status, user_id, created_at, start_date, end_date, days, users:user_id(name)"
            )

            if tab == "pending":
                lr_query = lr_query.eq("status", "pending").neq("user_id", user_id)
            elif tab == "mine":
                lr_query = lr_query.eq("user_id", user_id)
            elif tab == "handled":
                lr_query = lr_query.neq("status", "pending").neq("status", "cancelled")

            lr_query = lr_query.order("created_at", desc=True).limit(200)
            lr_result = await lr_query.execute()

            for item in lr_result.data or []:
                submitter = item.get("users")
                items.append(
                    {
                        "id": item["id"],
                        "source_table": "oa_leave_requests",
                        "type": "leave",
                        "description": item.get("reason", ""),
                        "amount": None,
                        "status": item.get("status", ""),
                        "submitted_by": item.get("user_id", ""),
                        "submitter_name": submitter.get("name") if isinstance(submitter, dict) else None,
                        "created_at": item.get("created_at", ""),
                        "leave_type": item.get("type"),
                        "start_date": item.get("start_date"),
                        "end_date": item.get("end_date"),
                        "days": item.get("days"),
                    }
                )

        # --- 3. 合并排序 + 分页 ---
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        total = len(items)
        start = (page - 1) * page_size
        paginated = items[start : start + page_size]

        return api_success(
            data={"items": paginated, "total": total, "page": page, "page_size": page_size},
            message="审批列表获取成功",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List approvals error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/tab-counts")
async def get_tab_counts(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """返回三个标签页的待处理计数。"""
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "需要组织上下文")

    client = getattr(request.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    try:
        # pending: approval_requests (exclude self-submitted)
        ar_pending = (
            await client.table("approval_requests")
            .select("id", count="exact")
            .eq("organization_id", org_id)
            .eq("status", "pending")
            .neq("submitted_by", user_id)
            .execute()
        )
        # pending: oa_leave_requests (exclude self-submitted)
        lr_pending = (
            await client.table("oa_leave_requests")
            .select("id", count="exact")
            .eq("status", "pending")
            .neq("user_id", user_id)
            .execute()
        )
        pending_count = (ar_pending.count or 0) + (lr_pending.count or 0)

        # mine: approval_requests
        ar_mine = (
            await client.table("approval_requests")
            .select("id", count="exact")
            .eq("organization_id", org_id)
            .eq("submitted_by", user_id)
            .execute()
        )
        # mine: oa_leave_requests
        lr_mine = await client.table("oa_leave_requests").select("id", count="exact").eq("user_id", user_id).execute()
        mine_count = (ar_mine.count or 0) + (lr_mine.count or 0)

        return api_success(
            data={"pending": pending_count, "mine": mine_count},
            message="标签页计数获取成功",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get tab counts error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---- 原有端点 ----


@router.post("/process", response_model=StandardResponse)
async def process_approval(request: ApprovalRequest, user_id: str = Depends(get_current_user_id)):
    """
    Process approval request via AI analysis and intelligent rule enforcement.

    1. AI context analysis (semantic understanding)
    2. Rule engine guardrails (hard limits)
    3. Auto-decision or manual escalation
    """
    try:
        # P4 Enhancement: Delegate to service layer
        decision = await ApprovalService.process_approval(request)

        return api_success(data=decision.model_dump(), message="Approval Processed")
    except Exception as e:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/submit-with-form")
async def submit_with_form(
    request: Request,
    body: SubmitWithFormRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Submit an approval request with custom form data.

    Workflow:
    1. Load the active form_schema for the given approval type
    2. Validate form_data against the schema
    3. Create the approval request (with form_data and form_schema_id)
    4. Route through the approval chain
    """
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "需要组织上下文")

    client = getattr(request.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    try:
        # 1. Load form schema for this approval type
        schema = await form_schema_service.get_schema_for_type(org_id, body.type, db=client)

        form_schema_id = None

        if schema:
            form_schema_id = schema.get("id")
            schema_fields = schema.get("fields", [])

            # 2. Validate form_data against schema
            if schema_fields and body.form_data:
                validation_errors = form_schema_service.validate_form_data(schema_fields, body.form_data)
                if validation_errors:
                    raise api_error(
                        ErrorCode.VALIDATION_INVALID_INPUT,
                        "表单数据校验失败",
                        details={"errors": validation_errors},
                    )
            elif schema_fields:
                # Schema exists but no form_data provided: check required fields
                validation_errors = form_schema_service.validate_form_data(schema_fields, {})
                if validation_errors:
                    raise api_error(
                        ErrorCode.VALIDATION_INVALID_INPUT,
                        "表单数据校验失败",
                        details={"errors": validation_errors},
                    )

        # 3. Match approval chain BEFORE creating the record
        chain_binding = await approval_chain_service.match_and_bind_chain(
            org_id=org_id,
            approval_type=body.type,
            amount=body.amount,
            db=client,
        )

        chain_id = chain_binding.get("chain_id")
        starting_step = chain_binding.get("starting_step", 0)
        approval_level = chain_binding.get("approval_level", "")
        timeout_at = chain_binding.get("timeout_at")
        auto_approve = chain_binding.get("auto_approve", False)

        # 4. Create approval request record in database
        insert_data = {
            "submitted_by": user_id,
            "type": body.type,
            "amount": body.amount,
            "description": body.details,
            "status": "approved" if auto_approve else "pending",
            "organization_id": org_id,
            "current_step": starting_step,
            "approval_level": approval_level,
        }

        if chain_id:
            insert_data["chain_id"] = chain_id
        if timeout_at:
            insert_data["timeout_at"] = timeout_at
        if body.form_data:
            insert_data["form_data"] = body.form_data
        if form_schema_id:
            insert_data["form_schema_id"] = form_schema_id
        if auto_approve:
            insert_data["ai_decision"] = "auto_approved"
            insert_data["approval_history"] = [
                {
                    "step": starting_step,
                    "decision": "auto_approved",
                    "approver_id": "system",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "comment": f"金额 ¥{body.amount} 在自动审批限额内",
                }
            ]

        result = await client.table("approval_requests").insert(insert_data).execute()

        if not result.data:
            raise api_error(ErrorCode.DB_QUERY_ERROR, "审批请求创建失败")

        created_request = result.data[0] if isinstance(result.data, list) else result.data
        request_id = created_request.get("id")

        # 5. Notify the correct approver (not broadcast)
        if not auto_approve:
            try:
                # Get requester name for notification
                user_res = await client.table("users").select("name").eq("id", user_id).maybe_single().execute()
                requester_name = user_res.data.get("name", "员工") if user_res.data else "员工"

                from app.tools.approval_tools import _notify_next_approver

                await _notify_next_approver(
                    client=client,
                    approval_level=approval_level,
                    requester_id=user_id,
                    requester_name=requester_name,
                    approval_type=body.type,
                    amount=body.amount,
                    req_id=request_id,
                    org_id=org_id,
                )
            except Exception as e:
                logger.warning(f"Failed to notify approver for form submission: {e}")

        return api_success(
            data={
                "request_id": request_id,
                "form_schema_id": form_schema_id,
                "chain_binding": chain_binding,
                "auto_approved": auto_approve,
                "approval_request": created_request,
            },
            message="审批请求已提交",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Submit with form failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ============== P0: Approval Chain Execution Endpoints ==============


@router.post("/{request_id}/advance")
async def advance_approval(
    request: Request,
    request_id: str,
    body: AdvanceDecisionRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    推进审批到下一步。

    根据审批链定义，将当前步骤的审批决定（approved/rejected）记录下来，
    并自动推进到下一步或最终完成审批。

    - approved: 如果还有后续步骤则推进，否则标记为最终通过
    - rejected: 立即终止审批流程
    """
    _org_id = getattr(request.state, "org_id", None)
    client = getattr(request.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    try:
        # 调用 approval_chain_service.advance_step 推进审批
        updated_request = await approval_chain_service.advance_step(
            request_id=request_id,
            decision=body.decision,
            approver_id=user_id,
            comment=body.comment,
            db=client,
        )

        # 根据决定发出相应事件
        from app.services.event_bus import EventType, emit

        if body.decision == "approved":
            new_status = updated_request.get("status", "pending")
            if new_status == "approved":
                # 审批链全部通过
                await emit(
                    EventType.APPROVAL_APPROVED.value,
                    {
                        "request_id": request_id,
                        "type": updated_request.get("type", ""),
                        "amount": updated_request.get("amount", 0),
                        "auto": False,
                    },
                    user_id=user_id,
                )
            else:
                # 推进到下一步
                await emit(
                    EventType.APPROVAL_ESCALATED.value,
                    {
                        "request_id": request_id,
                        "type": updated_request.get("type", ""),
                        "amount": updated_request.get("amount", 0),
                        "level": updated_request.get("approval_level", ""),
                        "current_step": updated_request.get("current_step", 0),
                    },
                    user_id=user_id,
                )
        elif body.decision == "rejected":
            await emit(
                EventType.APPROVAL_REJECTED.value,
                {
                    "request_id": request_id,
                    "type": updated_request.get("type", ""),
                    "amount": updated_request.get("amount", 0),
                    "reason": body.comment or "",
                },
                user_id=user_id,
            )

        return api_success(
            data={
                "request_id": request_id,
                "updated_request": updated_request,
                "decision": body.decision,
            },
            message="审批已推进" if body.decision == "approved" else "审批已驳回",
        )

    except RuntimeError as e:
        logger.warning(f"Advance approval failed: {e}")
        raise api_error(ErrorCode.RESOURCE_CONFLICT, str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Advance approval error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/{request_id}/progress")
async def get_approval_progress(
    request: Request,
    request_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    获取审批进度。

    返回审批链步骤定义 + 审批历史记录，展示当前进度。
    包含：chain_steps（流程定义）、history（审批记录）、current_step（当前步骤）、status（当前状态）。
    """
    client = getattr(request.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    try:
        # 获取审批请求
        req_result = await client.table("approval_requests").select("*").eq("id", request_id).maybe_single().execute()

        if not req_result.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, f"审批请求 {request_id} 不存在")

        request_data = req_result.data
        chain_id = request_data.get("chain_id")
        chain_steps = []

        # 如果有关联的审批链，获取步骤定义
        if chain_id:
            chain_result = (
                await client.table("approval_chains")
                .select("id, name, description, steps, applies_to")
                .eq("id", chain_id)
                .maybe_single()
                .execute()
            )
            if chain_result.data:
                chain_steps = chain_result.data.get("steps", [])

        # 审批历史
        history = request_data.get("approval_history", []) or []

        # 构建进度数据
        progress = {
            "request_id": request_id,
            "status": request_data.get("status", "pending"),
            "current_step": request_data.get("current_step", 0),
            "approval_level": request_data.get("approval_level"),
            "chain_id": chain_id,
            "chain_steps": chain_steps,
            "total_steps": len(chain_steps),
            "history": history,
            "timeout_at": request_data.get("timeout_at"),
            "escalated": request_data.get("escalated", False),
            "type": request_data.get("type"),
            "amount": request_data.get("amount"),
            "submitted_by": request_data.get("submitted_by"),
            "created_at": request_data.get("created_at"),
        }

        return api_success(data=progress, message="审批进度获取成功")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get approval progress error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/submit-smart")
async def submit_smart_approval(
    request: Request,
    body: SmartSubmitRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    智能提交审批 - 自动匹配工作流链。

    流程：
    1. 根据类型从数据库加载匹配的审批链
    2. 创建审批请求并关联 chain_id、current_step、approval_level、timeout_at
    3. 如果第一步是 AUTO 且金额在阈值内，自动批准
    4. 否则设置为 pending 并按链路由
    """
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "需要组织上下文")

    client = getattr(request.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    try:
        # 1. 匹配并绑定审批链
        chain_binding = await approval_chain_service.match_and_bind_chain(
            org_id=org_id,
            approval_type=body.type,
            amount=body.amount,
            db=client,
        )

        chain_id = chain_binding.get("chain_id")
        starting_step = chain_binding.get("starting_step", 0)
        approval_level = chain_binding.get("approval_level", "")
        timeout_at = chain_binding.get("timeout_at")
        auto_approve = chain_binding.get("auto_approve", False)

        # 2. 创建审批请求
        insert_data = {
            "submitted_by": user_id,
            "type": body.type,
            "amount": body.amount,
            "description": body.description,
            "status": "approved" if auto_approve else "pending",
            "organization_id": org_id,
            "current_step": starting_step,
            "approval_level": approval_level,
        }

        if chain_id:
            insert_data["chain_id"] = chain_id
        if timeout_at:
            insert_data["timeout_at"] = timeout_at
        if body.form_data:
            insert_data["form_data"] = body.form_data
        if auto_approve:
            insert_data["ai_decision"] = "auto_approved"
            insert_data["approval_history"] = [
                {
                    "step": starting_step,
                    "decision": "auto_approved",
                    "approver_id": "system",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "comment": f"金额 ¥{body.amount} 在自动审批限额内",
                }
            ]

        result = await client.table("approval_requests").insert(insert_data).execute()

        if not result.data:
            raise api_error(ErrorCode.DB_QUERY_ERROR, "审批请求创建失败")

        created_request = result.data[0] if isinstance(result.data, list) else result.data
        request_id = created_request.get("id")

        # 3. 发出事件
        from app.services.event_bus import EventType, emit

        if auto_approve:
            await emit(
                EventType.APPROVAL_APPROVED.value,
                {
                    "request_id": request_id,
                    "type": body.type,
                    "amount": body.amount,
                    "auto": True,
                },
                user_id=user_id,
            )
        else:
            await emit(
                EventType.APPROVAL_SUBMITTED.value,
                {
                    "request_id": request_id,
                    "type": body.type,
                    "amount": body.amount,
                    "level": approval_level,
                },
                user_id=user_id,
            )

        # 4. AI风险分析（异步，不阻塞主流程）
        risk_analysis = None
        try:
            risk_analysis = await ApprovalService.analyze_risk(
                request_type=body.type,
                amount=body.amount,
                description=body.description,
                user_id=user_id,
                org_id=org_id,
                db=client,
            )
        except Exception as e:
            logger.warning(f"AI risk analysis failed (non-blocking): {e}")

        return api_success(
            data={
                "request_id": request_id,
                "approval_request": created_request,
                "chain_binding": chain_binding,
                "auto_approved": auto_approve,
                "risk_analysis": risk_analysis,
            },
            message="审批请求已智能提交" if not auto_approve else "审批已自动通过",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Smart submit approval error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ============== Auto Approval Rules (#16) ==============


class AutoApprovalRuleCreate(BaseModel):
    name: str
    approval_type: str
    condition_field: str = "amount"
    condition_op: str = "lte"
    condition_value: float


@router.get("/auto-rules")
async def list_auto_rules(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取组织自动审批规则列表"""
    try:
        org_id = getattr(request.state, "org_id", None)
        if not org_id:
            return api_success(data=[], message="未关联组织")

        from app.core.database import supabase
        res = await (
            supabase.table("auto_approval_rules")
            .select("*")
            .eq("organization_id", org_id)
            .eq("is_active", True)
            .order("created_at", desc=True)
            .execute()
        )
        return api_success(data=res.data or [])
    except Exception as e:
        logger.error("List auto rules error: %s", e)
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/auto-rules")
async def create_auto_rule(
    body: AutoApprovalRuleCreate,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建自动审批规则（仅管理员）"""
    try:
        org_id = getattr(request.state, "org_id", None)
        role = getattr(request.state, "role", None)
        if role not in ("boss", "founder", "super_admin"):
            raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "仅管理员可管理自动审批规则")
        if not org_id:
            raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "未关联组织")

        from app.core.database import supabase
        res = await supabase.table("auto_approval_rules").insert({
            "organization_id": org_id,
            "name": body.name,
            "approval_type": body.approval_type,
            "condition_field": body.condition_field,
            "condition_op": body.condition_op,
            "condition_value": body.condition_value,
            "created_by": user_id,
        }).execute()

        return api_success(data=res.data[0] if res.data else None, message="自动审批规则已创建")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error("Create auto rule error: %s", e)
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.delete("/auto-rules/{rule_id}")
async def delete_auto_rule(
    rule_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """删除自动审批规则（软删除）"""
    try:
        org_id = getattr(request.state, "org_id", None)
        role = getattr(request.state, "role", None)
        if role not in ("boss", "founder", "super_admin"):
            raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "仅管理员可管理自动审批规则")

        from app.core.database import supabase
        res = await (
            supabase.table("auto_approval_rules")
            .update({"is_active": False})
            .eq("id", rule_id)
            .eq("organization_id", org_id)
            .execute()
        )
        if not res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "规则不存在")

        return api_success(data={"deleted": rule_id}, message="规则已删除")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error("Delete auto rule error: %s", e)
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
