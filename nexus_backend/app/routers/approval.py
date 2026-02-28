import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

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
    amount: float
    details: str
    form_data: dict[str, Any] = {}


class AdvanceDecisionRequest(BaseModel):
    """推进审批链的请求体"""

    decision: str = Field(..., pattern="^(approved|rejected)$", description="审批决定: approved 或 rejected")
    comment: str | None = Field(None, description="审批备注（可选）")


class SmartSubmitRequest(BaseModel):
    """智能提交审批请求 - 自动匹配工作流链"""

    type: str = Field(..., description="审批类型")
    amount: float = Field(..., gt=0, description="金额")
    description: str = Field(..., min_length=1, description="申请说明")
    form_data: dict[str, Any] = Field(default_factory=dict, description="表单数据")


# ============== Endpoints ==============


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
    org_id = getattr(request.state, "org_id", None)
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
        req_result = (
            await client.table("approval_requests")
            .select("*")
            .eq("id", request_id)
            .maybe_single()
            .execute()
        )

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
