import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from ._shared import CreateModelRequest, UpdateModelRequest, _mask_model_record
from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.encryption_service import encryption_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["LLM Models CRUD"])


@router.get("/models")
async def list_models(req: Request, user_id: str = Depends(get_current_user_id)):
    """获取当前租户的 LLM 模型配置列表"""
    try:
        db = getattr(req.state, "db", None)
        org_id = getattr(req.state, "org_id", None)

        if not db or not org_id:
            return api_success(data=[])

        result = (
            await db.table("llm_model_config")
            .select(
                "id,model_code,model_name,provider_type,adapter_code,"
                "api_base_url,api_key_encrypted,secret_key_encrypted,model_id,model_type,timeout_ms,max_tokens,"
                "context_window,supports_tools,supports_streaming,"
                "input_price_per_1m,output_price_per_1m,status,is_default,sort_order"
            )
            .eq("tenant_id", str(org_id))
            .eq("is_deleted", False)
            .order("sort_order")
            .execute()
        )
        
        # 对敏感数据进行脱敏处理
        masked_data = [_mask_model_record(r) for r in (result.data or [])]
        return api_success(data=masked_data)
    except Exception as e:
        logger.error(f"Failed to list LLM models: {e}")
        return api_success(data=[])


@router.post("/models")
async def create_model(req: Request, body: CreateModelRequest, user_id: str = Depends(get_current_user_id)):
    """创建新的 LLM 模型配置"""
    try:
        db = getattr(req.state, "db", None)
        org_id = getattr(req.state, "org_id", None)
        if not db or not org_id:
            raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        # 加密 API Key
        encrypted_key = encryption_service.encrypt(body.api_key) if body.api_key else None
        encrypted_secret = encryption_service.encrypt(body.secret_key) if body.secret_key else None

        data = body.model_dump(exclude={"api_key", "secret_key"})
        data.update({
            "tenant_id": str(org_id),
            "api_key_encrypted": encrypted_key,
            "secret_key_encrypted": encrypted_secret,
        })

        result = await db.table("llm_model_config").insert(data).execute()
        if not result.data:
            raise api_error(ErrorCode.DB_QUERY_ERROR, "创建模型失败")

        return api_success(data=_mask_model_record(result.data[0]), message="模型已添加")
    except Exception as e:
        logger.error(f"Failed to create model: {e}")
        if hasattr(e, "detail"): raise e
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/models/{model_id}")
async def update_model(
    model_id: str,
    req: Request,
    body: UpdateModelRequest,
    user_id: str = Depends(get_current_user_id)
):
    """更新 LLM 模型配置"""
    try:
        db = getattr(req.state, "db", None)
        org_id = getattr(req.state, "org_id", None)
        if not db or not org_id:
            raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        # 检查是否存在
        existing = await db.table("llm_model_config").select("id").eq("id", model_id).eq("tenant_id", str(org_id)).execute()
        if not existing.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "未找到该模型配置")

        update_data = body.model_dump(exclude_none=True, exclude={"api_key", "secret_key", "is_active"})
        
        # 处理开关字段映射 (is_active -> status)
        if body.is_active is not None:
            update_data["status"] = "enabled" if body.is_active else "disabled"

        # 如果提供了新的密钥，则加密
        if body.api_key is not None:
            update_data["api_key_encrypted"] = encryption_service.encrypt(body.api_key)
        if body.secret_key is not None:
            update_data["secret_key_encrypted"] = encryption_service.encrypt(body.secret_key)

        result = await db.table("llm_model_config").update(update_data).eq("id", model_id).execute()
        
        return api_success(data=_mask_model_record(result.data[0]), message="配置已更新")
    except Exception as e:
        logger.error(f"Failed to update model {model_id}: {e}")
        if hasattr(e, "detail"): raise e
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.delete("/models/{model_id}")
async def delete_model(model_id: str, req: Request, user_id: str = Depends(get_current_user_id)):
    """逻辑删除模型配置"""
    try:
        db = getattr(req.state, "db", None)
        org_id = getattr(req.state, "org_id", None)
        if not db or not org_id:
            raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        await db.table("llm_model_config").update({"is_deleted": True}).eq("id", model_id).eq("tenant_id", str(org_id)).execute()
        
        return api_success(data=None, message="模型已删除")
    except Exception as e:
        logger.error(f"Failed to delete model {model_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/models/{model_id}/test")
async def test_model(model_id: str, req: Request, user_id: str = Depends(get_current_user_id)):
    """测试模型连通性"""
    import httpx
    import time
    from app.services.encryption_service import encryption_service
    
    try:
        db = getattr(req.state, "db", None)
        org_id = getattr(req.state, "org_id", None)
        if not db or not org_id:
            raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        # 1. 获取模型配置
        res = await db.table("llm_model_config").select("*").eq("id", model_id).eq("tenant_id", str(org_id)).execute()
        if not res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "未找到该模型配置")
        
        config = res.data[0]
        base_url = config.get("api_base_url") or "https://api.openai.com/v1"
        # 确保 base_url 以 /v1 结尾（如果是 OpenAI 兼容）
        if not base_url.endswith("/v1") and "openai" in (config.get("provider_type") or "").lower():
            if not base_url.endswith("/"): base_url += "/"
            base_url += "v1"

        # 2. 解密 API Key
        encrypted_key = config.get("api_key_encrypted")
        api_key = ""
        if encrypted_key:
            try:
                api_key = encryption_service.decrypt(encrypted_key)
            except Exception as e:
                logger.error(f"Failed to decrypt API key for model {model_id}: {e}")
                raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "凭据解密失败，请重新输入 API Key")

        # 3. 发送测试请求 (调用 /models 接口验证有效性)
        start_time = time.time()
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            # 兼容性处理：有些供应商路径不同，尝试最通用的 /models
            test_url = f"{base_url.rstrip('/')}/models"
            
            try:
                resp = await client.get(test_url, headers=headers)
                latency = int((time.time() - start_time) * 1000)
                
                if resp.status_code == 200:
                    return api_success(data={"connectivity": "ok", "latency_ms": latency}, message="连通性测试通过")
                else:
                    return api_success(
                        data={"connectivity": "failed", "status_code": resp.status_code, "error": resp.text[:200]},
                        message=f"测试失败: 供应商返回状态码 {resp.status_code}"
                    )
            except Exception as net_err:
                return api_success(
                    data={"connectivity": "error", "error": str(net_err)},
                    message=f"网络连接失败: {str(net_err)}"
                )

    except Exception as e:
        logger.error(f"Model test error: {e}")
        if hasattr(e, "detail"): raise e
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
