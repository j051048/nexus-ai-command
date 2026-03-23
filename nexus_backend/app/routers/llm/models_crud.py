"""LLM Model CRUD endpoints — create, list, get, update, delete, test, toggle."""

import logging
import time

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import get_current_user_id
from app.core.config import settings
from app.core.errors import ErrorCode, api_error, api_list, api_success
from app.services.encryption_service import encryption_service

from ._shared import (
    CreateModelRequest,
    UpdateModelRequest,
    _get_admin_client,
    _mask_model_record,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/models")
async def create_model(
    body: CreateModelRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建新模型配置"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = _get_admin_client()

        # Resolve system defaults for quick-add
        actual_api_key = body.api_key
        if not actual_api_key or actual_api_key == "__SYSTEM_DEFAULT__":
            actual_api_key = settings.OPENAI_API_KEY

        actual_base_url = body.api_base_url
        if not actual_base_url:
            actual_base_url = settings.AI_BASE_URL

        # Encrypt sensitive fields
        encrypted_api_key = encryption_service.encrypt(actual_api_key)
        encrypted_secret_key = encryption_service.encrypt(body.secret_key) if body.secret_key else None

        record = {
            "tenant_id": org_id,
            "model_code": body.model_code,
            "model_name": body.model_name,
            "provider_type": body.provider_type,
            "adapter_code": body.adapter_code,
            "api_base_url": actual_base_url,
            "api_key_encrypted": encrypted_api_key,
            "secret_key_encrypted": encrypted_secret_key,
            "model_id": body.model_id or body.model_code,
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
        }

        res = await client.table("llm_model_config").insert(record).execute()
        model = res.data[0] if res.data else record
        return api_success(data={"model": _mask_model_record(model)}, message="模型配置创建成功")
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "LLM模型参数校验失败")
    except Exception as e:
        err_info = getattr(e, "details", str(e)) if hasattr(e, "code") else str(e)
        err_code = getattr(e, "code", "")
        if str(err_code) == "23505":
            # Check if there's a soft-deleted record with the same key — restore it instead of erroring
            try:
                deleted_res = (
                    await client.table("llm_model_config")
                    .select("id")
                    .eq("tenant_id", org_id)
                    .eq("model_code", body.model_code)
                    .eq("is_deleted", True)
                    .limit(1)
                    .execute()
                )
                if deleted_res.data:
                    # Restore the soft-deleted record with updated fields
                    restore_id = deleted_res.data[0]["id"]
                    record["is_deleted"] = False
                    record["status"] = body.status or "enabled"
                    restore_res = (
                        await client.table("llm_model_config")
                        .update(record)
                        .eq("id", restore_id)
                        .execute()
                    )
                    model = restore_res.data[0] if restore_res.data else record
                    return api_success(data={"model": _mask_model_record(model)}, message="模型配置已恢复")
            except Exception:
                pass
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "该模型已存在，请勿重复添加")
        logger.error(f"Create model error: user={user_id} err={err_info}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(err_info))


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
        client = _get_admin_client()

        # Build query for count
        count_query = (
            client.table("llm_model_config").select("id", count="exact").eq("tenant_id", org_id).eq("is_deleted", False)
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
            .eq("tenant_id", org_id)
            .eq("is_deleted", False)
            .order("create_time", desc=True)
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
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "LLM模型操作失败")


@router.get("/models/{model_id}")
async def get_model(
    model_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取单个模型详情"""
    try:
        client = _get_admin_client()

        res = (
            await client.table("llm_model_config")
            .select("*")
            .eq("id", model_id)
            .eq("is_deleted", False)
            .maybe_single()
            .execute()
        )
        if not res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "模型不存在")

        return api_success(data={"model": _mask_model_record(res.data)})
    except Exception as e:
        logger.error(f"Get model error: id={model_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "LLM模型操作失败")


@router.put("/models/{model_id}")
async def update_model(
    model_id: str,
    body: UpdateModelRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新模型配置"""
    try:
        client = _get_admin_client()

        update_data = body.model_dump(exclude_none=True)

        # Map frontend is_active boolean → DB status string
        if "is_active" in update_data:
            is_active = update_data.pop("is_active")
            if "status" not in update_data:
                update_data["status"] = "enabled" if is_active else "disabled"

        # Encrypt api_key if provided
        if "api_key" in update_data and update_data["api_key"]:
            update_data["api_key_encrypted"] = encryption_service.encrypt(update_data.pop("api_key"))
        # Encrypt secret_key if provided
        if "secret_key" in update_data and update_data["secret_key"]:
            update_data["secret_key_encrypted"] = encryption_service.encrypt(update_data.pop("secret_key"))

        if not update_data:
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "无更新内容")

        res = (
            await client.table("llm_model_config")
            .update(update_data)
            .eq("id", model_id)
            .eq("is_deleted", False)
            .execute()
        )
        if not res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "模型不存在")

        return api_success(data={"model": _mask_model_record(res.data[0])}, message="模型配置已更新")
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "LLM模型参数校验失败")
    except Exception as e:
        logger.error(f"Update model error: id={model_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "LLM模型操作失败")


@router.delete("/models/{model_id}")
async def delete_model(
    model_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """软删除模型（设置is_deleted=true）"""
    try:
        client = _get_admin_client()

        res = (
            await client.table("llm_model_config")
            .update({"is_deleted": True, "status": "disabled"})
            .eq("id", model_id)
            .eq("is_deleted", False)
            .execute()
        )
        if not res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "模型不存在")

        return api_success(data={"deleted": True}, message="模型已删除")
    except Exception as e:
        logger.error(f"Delete model error: id={model_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "LLM模型操作失败")


@router.post("/models/{model_id}/test")
async def test_model_connectivity(
    model_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """测试模型连通性"""
    try:
        client = _get_admin_client()

        res = (
            await client.table("llm_model_config")
            .select("*")
            .eq("id", model_id)
            .eq("is_deleted", False)
            .maybe_single()
            .execute()
        )
        if not res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "模型不存在")

        model_config = res.data

        # Decrypt api_key for testing
        decrypted_key = encryption_service.decrypt(model_config.get("api_key_encrypted", ""))

        # Import adapter and test connectivity
        start_time = time.time()
        test_success = False
        test_message = ""

        try:
            from app.services.llm_adapters.base import ModelConfig
            from app.services.llm_adapters.registry import get_adapter

            config = ModelConfig(
                model_code=model_config.get("model_code", ""),
                model_name=model_config.get("model_name", ""),
                provider_type=model_config.get("provider_type", ""),
                api_base_url=model_config.get("api_base_url", ""),
                api_key=decrypted_key,
                secret_key=model_config.get("secret_key_encrypted"),
                model_id=model_config.get("model_id", ""),
            )
            adapter = get_adapter(config.provider_type, config)
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

        return api_success(
            data={
                "model_id": model_id,
                "model_code": model_config.get("model_code"),
                "success": test_success,
                "message": test_message,
                "response_time_ms": elapsed_ms,
            }
        )
    except Exception as e:
        logger.error(f"Test model error: id={model_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "LLM模型操作失败")


@router.post("/models/{model_id}/toggle")
async def toggle_model_status(
    model_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """切换模型启用/禁用状态"""
    try:
        client = _get_admin_client()

        res = (
            await client.table("llm_model_config")
            .select("id, status")
            .eq("id", model_id)
            .eq("is_deleted", False)
            .maybe_single()
            .execute()
        )
        if not res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "模型不存在")

        current_status = res.data.get("status", "enabled")
        new_status = "disabled" if current_status == "enabled" else "enabled"

        await client.table("llm_model_config").eq("id", model_id).execute()

        return api_success(
            data={"model_id": model_id, "status": new_status},
            message=f"模型已{'启用' if new_status == 'enabled' else '禁用'}",
        )
    except Exception as e:
        logger.error(f"Toggle model error: id={model_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "LLM模型操作失败")
