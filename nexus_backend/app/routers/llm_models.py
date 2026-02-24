"""LLM Model Management API - Multi-model adaptation gateway management endpoints."""

import logging
import time
import uuid
from math import ceil

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_list, api_success
from app.services.encryption_service import encryption_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/llm", tags=["LLM Models"])


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------


class CreateModelRequest(BaseModel):
    model_code: str = Field(..., min_length=1, max_length=100, description="模型编码")
    model_name: str = Field(..., min_length=1, max_length=200, description="模型名称")
    provider_type: str = Field(..., min_length=1, max_length=50, description="供应商类型")
    adapter_code: str = Field(..., min_length=1, max_length=100, description="适配器编码")
    api_base_url: str = Field(..., min_length=1, max_length=500, description="API基础URL")
    api_key: str = Field(..., min_length=1, description="API密钥")
    secret_key: str | None = Field(None, description="Secret Key (部分供应商需要)")
    model_id: str | None = Field(None, max_length=200, description="供应商模型ID")
    timeout_ms: int = Field(30000, ge=1000, le=300000, description="超时时间(ms)")
    max_retries: int = Field(3, ge=0, le=10, description="最大重试次数")
    max_tokens: int = Field(4096, ge=1, description="最大Token数")
    context_window: int = Field(8192, ge=1, description="上下文窗口大小")
    supports_tools: bool = Field(False, description="是否支持工具调用")
    supports_streaming: bool = Field(True, description="是否支持流式输出")
    model_type: str = Field("chat", description="模型类型: chat/embedding/vision")
    input_price_per_1m: float = Field(0.0, ge=0, description="输入价格(每百万Token)")
    output_price_per_1m: float = Field(0.0, ge=0, description="输出价格(每百万Token)")
    default_temperature: float = Field(0.7, ge=0.0, le=2.0, description="默认温度")
    status: str = Field("active", description="状态: active/inactive")


class UpdateModelRequest(BaseModel):
    model_name: str | None = Field(None, max_length=200)
    provider_type: str | None = Field(None, max_length=50)
    adapter_code: str | None = Field(None, max_length=100)
    api_base_url: str | None = Field(None, max_length=500)
    api_key: str | None = Field(None, description="API密钥(不提供则保留原值)")
    secret_key: str | None = None
    model_id: str | None = Field(None, max_length=200)
    timeout_ms: int | None = Field(None, ge=1000, le=300000)
    max_retries: int | None = Field(None, ge=0, le=10)
    max_tokens: int | None = Field(None, ge=1)
    context_window: int | None = Field(None, ge=1)
    supports_tools: bool | None = None
    supports_streaming: bool | None = None
    model_type: str | None = None
    input_price_per_1m: float | None = Field(None, ge=0)
    output_price_per_1m: float | None = Field(None, ge=0)
    default_temperature: float | None = Field(None, ge=0.0, le=2.0)
    status: str | None = None


class CreateScheduleRuleRequest(BaseModel):
    rule_name: str = Field(..., min_length=1, max_length=200, description="规则名称")
    scene_code: str = Field(..., min_length=1, max_length=100, description="场景编码")
    agent_code: str | None = Field(None, max_length=100, description="Agent编码")
    primary_model_id: str = Field(..., description="主模型ID")
    backup_model_id: str | None = Field(None, description="备用模型ID")
    load_balance_strategy: str = Field("priority", description="负载均衡策略")
    priority: int = Field(0, ge=0, description="优先级")


class UpdateScheduleRuleRequest(BaseModel):
    rule_name: str | None = Field(None, max_length=200)
    scene_code: str | None = Field(None, max_length=100)
    agent_code: str | None = Field(None, max_length=100)
    primary_model_id: str | None = None
    backup_model_id: str | None = None
    load_balance_strategy: str | None = None
    priority: int | None = Field(None, ge=0)


class CreateQuotaConfigRequest(BaseModel):
    quota_type: str = Field(..., description="配额类型: user/org/model")
    target_id: str = Field(..., description="目标ID(用户ID/组织ID/模型ID)")
    max_tokens_per_day: int | None = Field(None, ge=0, description="每日最大Token数")
    max_requests_per_day: int | None = Field(None, ge=0, description="每日最大请求数")
    max_cost_per_day_usd: float | None = Field(None, ge=0, description="每日最大花费(USD)")
    max_tokens_per_month: int | None = Field(None, ge=0, description="每月最大Token数")
    max_cost_per_month_usd: float | None = Field(None, ge=0, description="每月最大花费(USD)")


class UpdateQuotaConfigRequest(BaseModel):
    max_tokens_per_day: int | None = Field(None, ge=0)
    max_requests_per_day: int | None = Field(None, ge=0)
    max_cost_per_day_usd: float | None = Field(None, ge=0)
    max_tokens_per_month: int | None = Field(None, ge=0)
    max_cost_per_month_usd: float | None = Field(None, ge=0)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _mask_api_key(key: str | None) -> str:
    """Mask API key for safe display: sk-****...****"""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:3]}****...****{key[-4:]}"


def _mask_model_record(record: dict) -> dict:
    """Mask sensitive fields in a model record before returning."""
    if not record:
        return record
    result = dict(record)
    if "api_key" in result and result["api_key"]:
        # Decrypt first to get real prefix/suffix for masking, then mask
        try:
            decrypted = encryption_service.decrypt(result["api_key"])
            result["api_key"] = _mask_api_key(decrypted)
        except Exception:
            result["api_key"] = "****"
    if "secret_key" in result and result["secret_key"]:
        result["secret_key"] = "****"
    return result


# ---------------------------------------------------------------------------
# Model CRUD endpoints
# ---------------------------------------------------------------------------


@router.post("/models")
async def create_model(
    body: CreateModelRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建新模型配置"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        # Encrypt sensitive fields
        encrypted_api_key = encryption_service.encrypt(body.api_key)
        encrypted_secret_key = encryption_service.encrypt(body.secret_key) if body.secret_key else None

        record = {
            "id": str(uuid.uuid4()),
            "org_id": org_id,
            "model_code": body.model_code,
            "model_name": body.model_name,
            "provider_type": body.provider_type,
            "adapter_code": body.adapter_code,
            "api_base_url": body.api_base_url,
            "api_key": encrypted_api_key,
            "secret_key": encrypted_secret_key,
            "model_id": body.model_id,
            "timeout_ms": body.timeout_ms,
            "max_retries": body.max_retries,
            "max_tokens": body.max_tokens,
            "context_window": body.context_window,
            "supports_tools": body.supports_tools,
            "supports_streaming": body.supports_streaming,
            "model_type": body.model_type,
            "input_price_per_1m": body.input_price_per_1m,
            "output_price_per_1m": body.output_price_per_1m,
            "default_temperature": body.default_temperature,
            "status": body.status,
            "is_deleted": False,
            "created_by": user_id,
        }

        res = await client.table("llm_model_config").insert(record).execute()
        model = res.data[0] if res.data else record
        return api_success(data={"model": _mask_model_record(model)}, message="模型配置创建成功")
    except ValueError as e:
        return api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
    except Exception as e:
        logger.error(f"Create model error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/models")
async def list_models(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    status: str | None = Query(None, description="状态筛选"),
    model_type: str | None = Query(None, description="模型类型筛选"),
    provider_type: str | None = Query(None, description="供应商类型筛选"),
):
    """获取模型列表（分页、筛选）"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        # Build query for count
        count_query = (
            client.table("llm_model_config")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .eq("is_deleted", False)
        )
        if status:
            count_query = count_query.eq("status", status)
        if model_type:
            count_query = count_query.eq("model_type", model_type)
        if provider_type:
            count_query = count_query.eq("provider_type", provider_type)
        count_res = await count_query.execute()
        total = count_res.count if count_res.count is not None else len(count_res.data or [])

        # Build query for data
        offset = (page - 1) * page_size
        data_query = (
            client.table("llm_model_config")
            .select("*")
            .eq("org_id", org_id)
            .eq("is_deleted", False)
            .order("created_at", desc=True)
            .range(offset, offset + page_size - 1)
        )
        if status:
            data_query = data_query.eq("status", status)
        if model_type:
            data_query = data_query.eq("model_type", model_type)
        if provider_type:
            data_query = data_query.eq("provider_type", provider_type)

        res = await data_query.execute()
        records = [_mask_model_record(r) for r in (res.data or [])]

        return api_list(items=records, total=total, page=page, page_size=page_size)
    except Exception as e:
        logger.error(f"List models error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/models/{model_id}")
async def get_model(
    model_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取单个模型详情"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        res = (
            await client.table("llm_model_config")
            .select("*")
            .eq("id", model_id)
            .eq("is_deleted", False)
            .maybe_single()
            .execute()
        )
        if not res.data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "模型不存在")

        return api_success(data={"model": _mask_model_record(res.data)})
    except Exception as e:
        logger.error(f"Get model error: id={model_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/models/{model_id}")
async def update_model(
    model_id: str,
    body: UpdateModelRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新模型配置"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        update_data = body.model_dump(exclude_none=True)

        # Encrypt api_key if provided
        if "api_key" in update_data and update_data["api_key"]:
            update_data["api_key"] = encryption_service.encrypt(update_data["api_key"])
        # Encrypt secret_key if provided
        if "secret_key" in update_data and update_data["secret_key"]:
            update_data["secret_key"] = encryption_service.encrypt(update_data["secret_key"])

        if not update_data:
            return api_error(ErrorCode.VALIDATION_INVALID_INPUT, "无更新内容")

        update_data["updated_by"] = user_id

        res = (
            await client.table("llm_model_config")
            .update(update_data)
            .eq("id", model_id)
            .eq("is_deleted", False)
            .execute()
        )
        if not res.data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "模型不存在")

        return api_success(data={"model": _mask_model_record(res.data[0])}, message="模型配置已更新")
    except ValueError as e:
        return api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
    except Exception as e:
        logger.error(f"Update model error: id={model_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.delete("/models/{model_id}")
async def delete_model(
    model_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """软删除模型（设置is_deleted=true）"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        res = (
            await client.table("llm_model_config")
            .update({"is_deleted": True, "updated_by": user_id})
            .eq("id", model_id)
            .eq("is_deleted", False)
            .execute()
        )
        if not res.data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "模型不存在")

        return api_success(message="模型已删除")
    except Exception as e:
        logger.error(f"Delete model error: id={model_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/models/{model_id}/test")
async def test_model_connectivity(
    model_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """测试模型连通性"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        res = (
            await client.table("llm_model_config")
            .select("*")
            .eq("id", model_id)
            .eq("is_deleted", False)
            .maybe_single()
            .execute()
        )
        if not res.data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "模型不存在")

        model_config = res.data

        # Decrypt api_key for testing
        decrypted_key = encryption_service.decrypt(model_config.get("api_key", ""))

        # Import adapter and test connectivity
        start_time = time.time()
        test_success = False
        test_message = ""

        try:
            from app.services.llm_adapters.base import get_adapter

            adapter = get_adapter(
                adapter_code=model_config["adapter_code"],
                api_base_url=model_config.get("api_base_url", ""),
                api_key=decrypted_key,
                model_id=model_config.get("model_id", ""),
            )
            test_result = await adapter.test_connectivity()
            test_success = test_result.get("success", False)
            test_message = test_result.get("message", "连通性测试完成")
        except ImportError:
            # If adapter module not available, do a basic HTTP check
            test_success = False
            test_message = "适配器模块未加载，无法执行连通性测试"
        except Exception as adapter_err:
            test_success = False
            test_message = f"连通性测试失败: {adapter_err}"

        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        return api_success(data={
            "model_id": model_id,
            "model_code": model_config.get("model_code"),
            "success": test_success,
            "message": test_message,
            "response_time_ms": elapsed_ms,
        })
    except Exception as e:
        logger.error(f"Test model error: id={model_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/models/{model_id}/toggle")
async def toggle_model_status(
    model_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """切换模型启用/禁用状态"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        res = (
            await client.table("llm_model_config")
            .select("id, status")
            .eq("id", model_id)
            .eq("is_deleted", False)
            .maybe_single()
            .execute()
        )
        if not res.data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "模型不存在")

        current_status = res.data.get("status", "active")
        new_status = "inactive" if current_status == "active" else "active"

        update_res = (
            await client.table("llm_model_config")
            .update({"status": new_status, "updated_by": user_id})
            .eq("id", model_id)
            .execute()
        )

        return api_success(
            data={"model_id": model_id, "status": new_status},
            message=f"模型已{'启用' if new_status == 'active' else '禁用'}",
        )
    except Exception as e:
        logger.error(f"Toggle model error: id={model_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---------------------------------------------------------------------------
# Adapter management endpoints
# ---------------------------------------------------------------------------


@router.get("/adapters")
async def list_adapters(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取可用适配器列表"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        res = await client.table("llm_adapter").select("*").order("adapter_code").execute()
        return api_success(data={"adapters": res.data or []})
    except Exception as e:
        logger.error(f"List adapters error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---------------------------------------------------------------------------
# Schedule rule management endpoints
# ---------------------------------------------------------------------------


@router.post("/schedule-rules")
async def create_schedule_rule(
    body: CreateScheduleRuleRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建调度规则"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        record = {
            "id": str(uuid.uuid4()),
            "org_id": org_id,
            "rule_name": body.rule_name,
            "scene_code": body.scene_code,
            "agent_code": body.agent_code,
            "primary_model_id": body.primary_model_id,
            "backup_model_id": body.backup_model_id,
            "load_balance_strategy": body.load_balance_strategy,
            "priority": body.priority,
            "created_by": user_id,
        }

        res = await client.table("llm_schedule_rule").insert(record).execute()
        rule = res.data[0] if res.data else record
        return api_success(data={"rule": rule}, message="调度规则创建成功")
    except Exception as e:
        logger.error(f"Create schedule rule error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/schedule-rules")
async def list_schedule_rules(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取调度规则列表"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        # Count
        count_res = (
            await client.table("llm_schedule_rule")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .execute()
        )
        total = count_res.count if count_res.count is not None else len(count_res.data or [])

        # Data
        offset = (page - 1) * page_size
        res = (
            await client.table("llm_schedule_rule")
            .select("*")
            .eq("org_id", org_id)
            .order("priority", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )

        return api_list(items=res.data or [], total=total, page=page, page_size=page_size)
    except Exception as e:
        logger.error(f"List schedule rules error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/schedule-rules/{rule_id}")
async def update_schedule_rule(
    rule_id: str,
    body: UpdateScheduleRuleRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新调度规则"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        update_data = body.model_dump(exclude_none=True)
        if not update_data:
            return api_error(ErrorCode.VALIDATION_INVALID_INPUT, "无更新内容")

        update_data["updated_by"] = user_id

        res = (
            await client.table("llm_schedule_rule")
            .update(update_data)
            .eq("id", rule_id)
            .execute()
        )
        if not res.data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "调度规则不存在")

        return api_success(data={"rule": res.data[0]}, message="调度规则已更新")
    except Exception as e:
        logger.error(f"Update schedule rule error: id={rule_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.delete("/schedule-rules/{rule_id}")
async def delete_schedule_rule(
    rule_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """删除调度规则"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        res = (
            await client.table("llm_schedule_rule")
            .delete()
            .eq("id", rule_id)
            .execute()
        )
        if not res.data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "调度规则不存在")

        return api_success(message="调度规则已删除")
    except Exception as e:
        logger.error(f"Delete schedule rule error: id={rule_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---------------------------------------------------------------------------
# Usage and cost endpoints
# ---------------------------------------------------------------------------


@router.get("/usage/stats")
async def get_usage_stats(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    start_date: str | None = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="结束日期 (YYYY-MM-DD)"),
    model_code: str | None = Query(None, description="模型编码"),
    scene_code: str | None = Query(None, description="场景编码"),
    agent_code: str | None = Query(None, description="Agent编码"),
    group_by: str = Query("day", description="分组维度: model/scene/agent/user/day"),
):
    """多维度用量统计"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        query = (
            client.table("llm_call_log")
            .select("*")
            .eq("org_id", org_id)
        )
        if start_date:
            query = query.gte("created_at", f"{start_date}T00:00:00")
        if end_date:
            query = query.lte("created_at", f"{end_date}T23:59:59")
        if model_code:
            query = query.eq("model_code", model_code)
        if scene_code:
            query = query.eq("scene_code", scene_code)
        if agent_code:
            query = query.eq("agent_code", agent_code)

        res = await query.order("created_at", desc=True).execute()
        logs = res.data or []

        # Aggregate by group_by dimension
        stats: dict = {}
        for log in logs:
            if group_by == "model":
                key = log.get("model_code", "unknown")
            elif group_by == "scene":
                key = log.get("scene_code", "unknown")
            elif group_by == "agent":
                key = log.get("agent_code", "unknown")
            elif group_by == "user":
                key = log.get("user_id", "unknown")
            else:  # day
                key = str(log.get("created_at", ""))[:10]

            if key not in stats:
                stats[key] = {
                    "group": key,
                    "total_calls": 0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cost": 0.0,
                    "success_count": 0,
                    "error_count": 0,
                }
            stats[key]["total_calls"] += 1
            stats[key]["total_input_tokens"] += log.get("input_tokens", 0) or 0
            stats[key]["total_output_tokens"] += log.get("output_tokens", 0) or 0
            stats[key]["total_cost"] += float(log.get("cost", 0) or 0)
            if log.get("status") == "success":
                stats[key]["success_count"] += 1
            else:
                stats[key]["error_count"] += 1

        return api_success(data={
            "group_by": group_by,
            "stats": list(stats.values()),
            "total_records": len(logs),
        })
    except Exception as e:
        logger.error(f"Usage stats error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/usage/cost-report")
async def get_cost_report(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    start_date: str | None = Query(None, description="开始日期"),
    end_date: str | None = Query(None, description="结束日期"),
):
    """成本报告（含分类明细）"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        query = client.table("llm_call_log").select("*").eq("org_id", org_id)
        if start_date:
            query = query.gte("created_at", f"{start_date}T00:00:00")
        if end_date:
            query = query.lte("created_at", f"{end_date}T23:59:59")

        res = await query.execute()
        logs = res.data or []

        total_cost = 0.0
        by_model: dict = {}
        by_scene: dict = {}
        for log in logs:
            cost = float(log.get("cost", 0) or 0)
            total_cost += cost

            model = log.get("model_code", "unknown")
            by_model[model] = by_model.get(model, 0.0) + cost

            scene = log.get("scene_code", "unknown")
            by_scene[scene] = by_scene.get(scene, 0.0) + cost

        return api_success(data={
            "total_cost": round(total_cost, 4),
            "total_calls": len(logs),
            "by_model": [{"model": k, "cost": round(v, 4)} for k, v in sorted(by_model.items(), key=lambda x: -x[1])],
            "by_scene": [{"scene": k, "cost": round(v, 4)} for k, v in sorted(by_scene.items(), key=lambda x: -x[1])],
        })
    except Exception as e:
        logger.error(f"Cost report error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/usage/model-ranking")
async def get_model_ranking(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50, description="排名数量"),
):
    """模型使用排行"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        query = client.table("llm_call_log").select("*").eq("org_id", org_id)
        if start_date:
            query = query.gte("created_at", f"{start_date}T00:00:00")
        if end_date:
            query = query.lte("created_at", f"{end_date}T23:59:59")

        res = await query.execute()
        logs = res.data or []

        ranking: dict = {}
        for log in logs:
            model = log.get("model_code", "unknown")
            if model not in ranking:
                ranking[model] = {
                    "model_code": model,
                    "call_count": 0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                }
            ranking[model]["call_count"] += 1
            ranking[model]["total_tokens"] += (log.get("input_tokens", 0) or 0) + (log.get("output_tokens", 0) or 0)
            ranking[model]["total_cost"] += float(log.get("cost", 0) or 0)

        sorted_ranking = sorted(ranking.values(), key=lambda x: x["call_count"], reverse=True)[:limit]

        return api_success(data={"ranking": sorted_ranking})
    except Exception as e:
        logger.error(f"Model ranking error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ---------------------------------------------------------------------------
# Quota management endpoints
# ---------------------------------------------------------------------------


@router.get("/quota-configs")
async def list_quota_configs(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取配额配置列表"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        res = (
            await client.table("llm_quota_config")
            .select("*")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .execute()
        )
        return api_success(data={"configs": res.data or []})
    except Exception as e:
        logger.error(f"List quota configs error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/quota-configs")
async def create_quota_config(
    body: CreateQuotaConfigRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建配额配置"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        record = {
            "id": str(uuid.uuid4()),
            "org_id": org_id,
            "quota_type": body.quota_type,
            "target_id": body.target_id,
            "max_tokens_per_day": body.max_tokens_per_day,
            "max_requests_per_day": body.max_requests_per_day,
            "max_cost_per_day_usd": body.max_cost_per_day_usd,
            "max_tokens_per_month": body.max_tokens_per_month,
            "max_cost_per_month_usd": body.max_cost_per_month_usd,
            "created_by": user_id,
        }

        res = await client.table("llm_quota_config").insert(record).execute()
        config = res.data[0] if res.data else record
        return api_success(data={"config": config}, message="配额配置创建成功")
    except Exception as e:
        logger.error(f"Create quota config error: user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/quota-configs/{config_id}")
async def update_quota_config(
    config_id: str,
    body: UpdateQuotaConfigRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新配额配置"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            return api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        update_data = body.model_dump(exclude_none=True)
        if not update_data:
            return api_error(ErrorCode.VALIDATION_INVALID_INPUT, "无更新内容")

        update_data["updated_by"] = user_id

        res = (
            await client.table("llm_quota_config")
            .update(update_data)
            .eq("id", config_id)
            .execute()
        )
        if not res.data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "配额配置不存在")

        return api_success(data={"config": res.data[0]}, message="配额配置已更新")
    except Exception as e:
        logger.error(f"Update quota config error: id={config_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
