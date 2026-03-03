"""VMD Task Management API - Multi-agent task orchestration endpoints."""

import json
import logging
import uuid
from datetime import UTC, datetime

from app.services.ai_service import AIService

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_list, api_success
from app.models.response_models import VMDSubTaskResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vmd", tags=["VMD Tasks"])


def _get_admin_client():
    """Get the global service-key Supabase client (bypasses RLS)."""
    from app.core.database import supabase

    if not supabase:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")
    return supabase


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------


class CreateTaskRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500, description="任务标题")
    description: str = Field(..., min_length=1, description="任务描述（自然语言输入）")
    scene_code: str = Field(..., min_length=1, max_length=100, description="场景编码")
    priority: str = Field("medium", description="优先级: low/medium/high/urgent")
    deadline: str | None = Field(None, description="截止时间 (ISO格式)")


class AuditSubTaskRequest(BaseModel):
    action: str = Field(..., description="审核操作: approve/reject")
    comment: str | None = Field(None, max_length=2000, description="审核意见")


class UpdateAgentConfigRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    system_prompt: str | None = Field(None, description="系统提示词")
    tool_whitelist: list[str] | None = Field(None, description="工具白名单")
    scene_codes: list[str] | None = Field(None, description="适用场景编码列表")
    is_active: bool | None = Field(None, description="是否启用")
    recommended_model_tier: str | None = Field(None, description="模型层级: high/standard")
    max_retries: int | None = Field(None, ge=0, le=10, description="最大重试次数")
    timeout_ms: int | None = Field(None, ge=1000, le=600000, description="超时时间(ms)")
    model_code: str | None = Field(None, max_length=100, description="指定模型编码")
    status: str | None = Field(None, description="状态: active/inactive")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _generate_task_code() -> str:
    """Generate a unique task code: VMD-YYYYMMDD-XXXX"""
    date_part = datetime.utcnow().strftime("%Y%m%d")
    short_id = uuid.uuid4().hex[:6].upper()
    return f"VMD-{date_part}-{short_id}"


# ---------------------------------------------------------------------------
# Task CRUD endpoints
# ---------------------------------------------------------------------------


@router.post("/tasks")
async def create_task(
    body: CreateTaskRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建VMD任务"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        admin = _get_admin_client()

        record = {
            "tenant_id": org_id,
            "task_code": _generate_task_code(),
            "title": body.title,
            "description": body.description,
            "scene_code": body.scene_code,
            "priority": body.priority,
            "deadline": body.deadline,
            "status": "pending",
            "user_id": user_id,
        }

        res = await admin.table("vmd_main_task").insert(record).execute()
        task = res.data[0] if res.data else record
        task_id = task.get("id", record.get("id", ""))

        # -------------------------------------------------------------
        # Synchronous LLM WBS Decomposition (no celery)
        # -------------------------------------------------------------
        decompose_prompt = (
            f"你是一个项目分解专家。请将以下任务分解为可执行的子任务列表。\n\n"
            f"任务标题: {body.title}\n"
            f"任务描述: {body.description}\n"
            f"场景编码: {body.scene_code}\n\n"
            f"请返回JSON格式的子任务列表，每个子任务包含:\n"
            f"- title: 子任务标题\n"
            f"- agent_role: 负责的Agent角色 (如: content_creator, data_analyst, market_researcher, reviewer)\n"
            f"- description: 子任务描述\n"
            f"- sort_order: 执行顺序 (从1开始)\n\n"
            f"只返回JSON数组，不要其他内容。示例:\n"
            f'[{{"title": "市场调研", "agent_role": "market_researcher", "description": "...", "sort_order": 1}}]'
        )

        sub_tasks_data = []
        try:
            llm_response = await AIService.call_llm(
                decompose_prompt,
                "你是一个严格按JSON格式输出的项目分解助手。只输出JSON数组，不添加任何其他文字。"
            )

            # Parse LLM response - try to extract JSON array
            response_text = llm_response.strip()
            # Handle markdown code blocks
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                # Remove first and last lines if they are code block markers
                response_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                response_text = response_text.strip()

            sub_tasks_data = json.loads(response_text)
            if not isinstance(sub_tasks_data, list):
                sub_tasks_data = [sub_tasks_data]

        except Exception as e:
            logger.warning(f"decompose_vmd_task: LLM response parse failed: {e}, creating default sub-task")
            sub_tasks_data = [
                {
                    "title": f"执行: {body.title}",
                    "agent_role": "content_creator",
                    "description": body.description,
                    "sort_order": 1,
                }
            ]

        # Create vmd_sub_task records
        created_count = 0
        for st in sub_tasks_data:
            try:
                sub_record = {
                    "main_task_id": task_id,
                    "tenant_id": org_id,
                    "title": st.get("title", "未命名子任务"),
                    "agent_code": st.get("agent_role", "content_creator"),
                    "description": st.get("description", ""),
                    "sort_order": st.get("sort_order", created_count + 1),
                    "status": "pending",
                }
                await admin.table("vmd_sub_task").insert(sub_record).execute()
                created_count += 1
            except Exception as e:
                logger.error(f"decompose_vmd_task: failed to create sub-task: {e}")

        # Update main task status and WBS structure
        wbs_structure = {
            "version": "1.0",
            "decomposed_at": datetime.now(UTC).isoformat(),
            "total_sub_tasks": created_count,
            "sub_tasks": [
                {"title": st.get("title", ""), "agent_role": st.get("agent_role", "")}
                for st in sub_tasks_data[:created_count]
            ],
        }

        update_res = await (
            admin.table("vmd_main_task")
            .update(
                {
                    "status": "executing",
                    "wbs_structure": wbs_structure,
                }
            )
            .eq("id", task_id)
            .execute()
        )
        if update_res.data:
            task = update_res.data[0]

        return api_success(data={"task": task}, message="任务创建成功且子任务分解完成")
    except Exception as e:
        logger.error(f"Create task error: user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/tasks")
async def list_tasks(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    status: str | None = Query(None, description="状态筛选"),
    priority: str | None = Query(None, description="优先级筛选"),
    scene_code: str | None = Query(None, description="场景编码筛选"),
):
    """获取任务列表"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        admin = _get_admin_client()

        # Count query
        count_query = admin.table("vmd_main_task").select("id", count="exact").eq("tenant_id", org_id)
        if status:
            count_query = count_query.eq("status", status)
        if priority:
            count_query = count_query.eq("priority", priority)
        if scene_code:
            count_query = count_query.eq("scene_code", scene_code)

        count_res = await count_query.execute()
        total = count_res.count if count_res.count is not None else len(count_res.data or [])

        # Data query
        offset = (page - 1) * page_size
        data_query = (
            admin.table("vmd_main_task")
            .select("*")
            .eq("tenant_id", org_id)
            .order("create_time", desc=True)
            .range(offset, offset + page_size - 1)
        )
        if status:
            data_query = data_query.eq("status", status)
        if priority:
            data_query = data_query.eq("priority", priority)
        if scene_code:
            data_query = data_query.eq("scene_code", scene_code)

        res = await data_query.execute()
        return api_list(items=res.data or [], total=total, page=page, page_size=page_size)
    except Exception as e:
        logger.error(f"List tasks error: user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取任务详情（含子任务、WBS结构、进度信息）— 返回扁平结构"""
    try:
        admin = _get_admin_client()

        # Get main task
        task_res = await admin.table("vmd_main_task").select("*").eq("id", task_id).maybe_single().execute()
        if not task_res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "任务不存在")

        task = task_res.data

        # Get sub-tasks
        sub_tasks_res = (
            await admin.table("vmd_sub_task")
            .select("*")
            .eq("main_task_id", task_id)
            .order("sort_order", desc=False)
            .execute()
        )
        sub_tasks = sub_tasks_res.data or []

        # Calculate progress as a flat number (percentage)
        total_sub = len(sub_tasks)
        completed_sub = sum(1 for s in sub_tasks if s.get("status") == "completed")
        progress = round((completed_sub / total_sub * 100), 1) if total_sub > 0 else 0.0

        # Build flat response using response model
        flat_response = {
            **task,
            "progress": progress,  # Always a number, never a nested object
            "total_sub_tasks": total_sub,
            "completed_sub_tasks": completed_sub,
            "sub_tasks": [
                VMDSubTaskResponse(
                    id=s.get("id", ""),
                    agent_role=s.get("agent_role", ""),
                    title=s.get("title", ""),
                    status=s.get("status", "pending"),
                    output=s.get("output"),
                    sort_order=s.get("sort_order", 0),
                    review_status=s.get("review_status"),
                ).model_dump()
                for s in sub_tasks
            ],
        }

        return api_success(data=flat_response)
    except Exception as e:
        logger.error(f"Get task error: id={task_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/tasks/{task_id}/logs")
async def get_task_logs(
    task_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """获取任务执行日志"""
    try:
        admin = _get_admin_client()

        # Count
        count_res = await admin.table("llm_call_log").select("id", count="exact").eq("main_task_id", task_id).execute()
        total = count_res.count if count_res.count is not None else len(count_res.data or [])

        # Data
        offset = (page - 1) * page_size
        res = (
            await admin.table("llm_call_log")
            .select("*")
            .eq("main_task_id", task_id)
            .order("create_time", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )

        return api_list(items=res.data or [], total=total, page=page, page_size=page_size)
    except Exception as e:
        logger.error(f"Get task logs error: task={task_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---------------------------------------------------------------------------
# Task lifecycle endpoints
# ---------------------------------------------------------------------------


@router.post("/tasks/{task_id}/pause")
async def pause_task(
    task_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """暂停任务"""
    try:
        admin = _get_admin_client()

        # Verify task exists and is in executable state
        task_res = await admin.table("vmd_main_task").select("id, status").eq("id", task_id).maybe_single().execute()
        if not task_res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "任务不存在")

        current_status = task_res.data.get("status")
        if current_status not in ("pending", "executing"):
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, f"当前状态({current_status})不允许暂停")

        await (
            admin.table("vmd_main_task").update({"status": "paused", "updated_by": user_id}).eq("id", task_id).execute()
        )
        return api_success(data={"task_id": task_id, "status": "paused"}, message="任务已暂停")
    except Exception as e:
        logger.error(f"Pause task error: id={task_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/tasks/{task_id}/resume")
async def resume_task(
    task_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """恢复任务"""
    try:
        admin = _get_admin_client()

        task_res = await admin.table("vmd_main_task").select("id, status").eq("id", task_id).maybe_single().execute()
        if not task_res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "任务不存在")

        if task_res.data.get("status") != "paused":
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "只有暂停状态的任务可以恢复")

        await (
            admin.table("vmd_main_task")
            .update({"status": "executing", "updated_by": user_id})
            .eq("id", task_id)
            .execute()
        )
        return api_success(data={"task_id": task_id, "status": "executing"}, message="任务已恢复执行")
    except Exception as e:
        logger.error(f"Resume task error: id={task_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """取消任务"""
    try:
        admin = _get_admin_client()

        task_res = await admin.table("vmd_main_task").select("id, status").eq("id", task_id).maybe_single().execute()
        if not task_res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "任务不存在")

        current_status = task_res.data.get("status")
        if current_status in ("completed", "cancelled"):
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, f"当前状态({current_status})不允许取消")

        await (
            admin.table("vmd_main_task")
            .update({"status": "cancelled", "updated_by": user_id})
            .eq("id", task_id)
            .execute()
        )
        return api_success(data={"task_id": task_id, "status": "cancelled"}, message="任务已取消")
    except Exception as e:
        logger.error(f"Cancel task error: id={task_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/tasks/{task_id}/retry")
async def retry_task(
    task_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """重试失败的子任务"""
    try:
        admin = _get_admin_client()

        # Verify task exists
        task_res = await admin.table("vmd_main_task").select("id, status").eq("id", task_id).maybe_single().execute()
        if not task_res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "任务不存在")

        # Find failed sub-tasks
        failed_res = (
            await admin.table("vmd_sub_task").select("id").eq("main_task_id", task_id).eq("status", "failed").execute()
        )
        failed_sub_tasks = failed_res.data or []

        if not failed_sub_tasks:
            return api_success(data={"retried_count": 0}, message="没有需要重试的失败子任务")

        # Reset failed sub-tasks to pending
        failed_ids = [s["id"] for s in failed_sub_tasks]
        for sub_id in failed_ids:
            await (
                admin.table("vmd_sub_task")
                .update({"status": "pending", "retry_count": 0, "error_message": None, "updated_by": user_id})
                .eq("id", sub_id)
                .execute()
            )

        # Set main task back to executing
        await (
            admin.table("vmd_main_task")
            .update({"status": "executing", "updated_by": user_id})
            .eq("id", task_id)
            .execute()
        )

        return api_success(
            data={"task_id": task_id, "retried_count": len(failed_ids), "status": "executing"},
            message=f"已重新提交 {len(failed_ids)} 个失败子任务",
        )
    except Exception as e:
        logger.error(f"Retry task error: id={task_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---------------------------------------------------------------------------
# Sub-task audit endpoint
# ---------------------------------------------------------------------------


@router.post("/sub-tasks/{sub_task_id}/audit")
async def audit_sub_task(
    sub_task_id: str,
    body: AuditSubTaskRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """审核子任务"""
    try:
        admin = _get_admin_client()

        if body.action not in ("approve", "reject"):
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "action 必须为 approve 或 reject")

        # Verify sub-task exists
        sub_res = (
            await admin.table("vmd_sub_task")
            .select("id, status, main_task_id")
            .eq("id", sub_task_id)
            .maybe_single()
            .execute()
        )
        if not sub_res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "子任务不存在")

        if body.action == "approve":
            update_data = {
                "review_status": "approved",
                "review_comment": body.comment,
                "reviewed_by": user_id,
                "reviewed_at": datetime.utcnow().isoformat(),
            }
        else:
            update_data = {
                "review_status": "rejected",
                "review_comment": body.comment,
                "reviewed_by": user_id,
                "reviewed_at": datetime.utcnow().isoformat(),
                "status": "pending",  # Allow re-execution
            }

        await admin.table("vmd_sub_task").update(update_data).eq("id", sub_task_id).execute()

        return api_success(
            data={"sub_task_id": sub_task_id, "review_status": update_data["review_status"]},
            message=f"子任务已{'通过' if body.action == 'approve' else '驳回'}",
        )
    except Exception as e:
        logger.error(f"Audit sub-task error: id={sub_task_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


class SubmitSubTaskRequest(BaseModel):
    output: str

@router.post("/sub-tasks/{sub_task_id}/submit")
async def submit_sub_task(
    sub_task_id: str,
    body: SubmitSubTaskRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """人工与AI协作完成后，提交子任务的最终输出结果"""
    try:
        admin = _get_admin_client()

        # Verify sub-task exists
        sub_res = (
            await admin.table("vmd_sub_task")
            .select("id, status")
            .eq("id", sub_task_id)
            .maybe_single()
            .execute()
        )
        if not sub_res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "子任务不存在")

        update_data = {
            "status": "completed",
            "review_status": "pending",  # Auto-push to reviewing state
            "output_content": body.output,
            "update_time": datetime.now(UTC).isoformat(),
        }

        await admin.table("vmd_sub_task").update(update_data).eq("id", sub_task_id).execute()

        return api_success(
            data={"sub_task_id": sub_task_id, "status": "completed", "review_status": "pending"},
            message="子任务输出已提交，等待审核",
        )
    except Exception as e:
        logger.error(f"Submit sub-task error: id={sub_task_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---------------------------------------------------------------------------
# Agent config endpoints
# ---------------------------------------------------------------------------


@router.get("/agents/config")
async def list_agent_configs(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取所有Agent角色配置（优先租户自定义，回退全局默认，最终回退代码默认）"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        admin = _get_admin_client()

        # 1. Query global defaults (tenant_id IS NULL)
        global_agents: dict[str, dict] = {}
        try:
            res = (
                await admin.table("vmd_agent_config").select("*").is_("tenant_id", "null").order("sort_order").execute()
            )
            for a in res.data or []:
                global_agents[a["agent_code"]] = a
        except Exception:
            pass

        # 2. Query tenant-specific overrides
        tenant_agents: dict[str, dict] = {}
        try:
            res = (
                await admin.table("vmd_agent_config").select("*").eq("tenant_id", org_id).order("sort_order").execute()
            )
            for a in res.data or []:
                tenant_agents[a["agent_code"]] = a
        except Exception:
            pass

        # 3. Merge: tenant overrides take priority over global defaults
        if global_agents:
            merged = {}
            for code, agent in global_agents.items():
                merged[code] = tenant_agents.pop(code, None) or agent
            # Append any tenant-only agents not in global defaults
            for code, agent in tenant_agents.items():
                merged[code] = agent
            agents = sorted(merged.values(), key=lambda x: x.get("sort_order", 0))
        elif tenant_agents:
            agents = sorted(tenant_agents.values(), key=lambda x: x.get("sort_order", 0))
        else:
            agents = []

        # 4. Final fallback: use Python role registry code defaults
        if not agents:
            from app.agent.roles.registry import ROLE_REGISTRY

            agents = []
            for i, (code, role) in enumerate(ROLE_REGISTRY.items()):
                agents.append(
                    {
                        "id": f"code-default-{code}",
                        "agent_code": code,
                        "agent_name": role.agent_name,
                        "agent_role": role.system_prompt[:100] if role.system_prompt else "",
                        "system_prompt": role.system_prompt,
                        "tool_whitelist": role.tool_whitelist,
                        "scene_codes": role.scene_codes,
                        "recommended_model_tier": role.recommended_model_tier,
                        "is_active": True,
                        "sort_order": i,
                    }
                )

        return api_success(data={"agents": agents})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List agent configs error: user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/agents/config/{agent_code}")
async def update_agent_config(
    agent_code: str,
    body: UpdateAgentConfigRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新Agent配置（租户级覆写，首次编辑时从全局默认或代码默认复制）"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        admin = _get_admin_client()

        update_data = body.model_dump(exclude_none=True)
        if not update_data:
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "无更新内容")

        update_data["updated_by"] = user_id

        # Try updating tenant-specific row first
        res = (
            await admin.table("vmd_agent_config")
            .update(update_data)
            .eq("agent_code", agent_code)
            .eq("tenant_id", org_id)
            .execute()
        )

        if not res.data:
            # No tenant row exists — try to copy from global default
            base = None
            try:
                global_res = (
                    await admin.table("vmd_agent_config")
                    .select("*")
                    .eq("agent_code", agent_code)
                    .is_("tenant_id", "null")
                    .limit(1)
                    .execute()
                )
                if global_res.data:
                    base = global_res.data[0]
            except Exception:
                pass

            # If DB global default not found, use Python role registry
            if not base:
                from app.agent.roles.registry import ROLE_REGISTRY

                role = ROLE_REGISTRY.get(agent_code)
                if not role:
                    raise api_error(ErrorCode.RESOURCE_NOT_FOUND, f"Agent配置不存在: {agent_code}")
                base = {
                    "agent_code": role.agent_code,
                    "agent_name": role.agent_name,
                    "system_prompt": role.system_prompt,
                    "tool_whitelist": role.tool_whitelist,
                    "scene_codes": role.scene_codes,
                    "recommended_model_tier": role.recommended_model_tier,
                    "is_active": True,
                    "sort_order": 0,
                }

            # Clone the base config for this tenant
            new_row = {k: v for k, v in base.items() if k not in ("id", "create_time", "update_time")}
            new_row["tenant_id"] = org_id
            new_row.update(update_data)

            res = await admin.table("vmd_agent_config").insert(new_row).execute()
            if not res.data:
                raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "创建租户Agent配置失败")

        return api_success(data={"agent": res.data[0]}, message="Agent配置已更新")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update agent config error: code={agent_code} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
