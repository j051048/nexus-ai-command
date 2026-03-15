"""Shared helpers, Pydantic models, and constants for LLM sub-routers."""

import logging

from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import ErrorCode, api_error
from app.services.encryption_service import encryption_service

logger = logging.getLogger(__name__)


def _get_admin_client():
    """Get the global service-key Supabase client (bypasses RLS)."""
    from app.core.database import supabase

    if not supabase:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")
    return supabase


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------


class CreateModelRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_code: str = Field(..., min_length=1, max_length=100, description="模型编码")
    model_name: str = Field(..., min_length=1, max_length=200, description="模型名称")
    provider_type: str = Field(..., min_length=1, max_length=50, description="供应商类型")
    adapter_code: str = Field(..., min_length=1, max_length=100, description="适配器编码")
    api_base_url: str = Field("", max_length=500, description="API基础URL (空则使用系统默认)")
    api_key: str = Field("", description="API密钥 (空或__SYSTEM_DEFAULT__则使用系统默认)")
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
    status: str = Field("enabled", description="状态: enabled/disabled")


class UpdateModelRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

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
    is_active: bool | None = None


class CreateScheduleRuleRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    rule_name: str = Field(..., min_length=1, max_length=200, description="规则名称")
    scene_code: str = Field(..., min_length=1, max_length=100, description="场景编码")
    agent_code: str | None = Field(None, max_length=100, description="Agent编码")
    primary_model_id: str = Field(..., description="主模型ID")
    backup_model_id: str | None = Field(None, description="备用模型ID")
    load_balance_strategy: str = Field("priority", description="负载均衡策略")
    priority: int = Field(0, ge=0, description="优先级")
    complexity_tier: str | None = Field(
        None,
        description="复杂度层级: economy/balanced/power/flagship",
        pattern=r"^(economy|balanced|power|flagship)$",
    )


class UpdateScheduleRuleRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    rule_name: str | None = Field(None, max_length=200)
    scene_code: str | None = Field(None, max_length=100)
    agent_code: str | None = Field(None, max_length=100)
    primary_model_id: str | None = None
    backup_model_id: str | None = None
    load_balance_strategy: str | None = None
    priority: int | None = Field(None, ge=0)
    complexity_tier: str | None = Field(
        None,
        description="复杂度层级: economy/balanced/power/flagship",
        pattern=r"^(economy|balanced|power|flagship)$",
    )


class CreateQuotaConfigRequest(BaseModel):
    quota_type: str = Field(..., description="配额类型: user/org/model")
    target_id: str = Field(..., description="目标ID(用户ID/组织ID/模型ID)")
    daily_token_limit: int | None = Field(None, ge=0, description="每日最大Token数")
    daily_request_limit: int | None = Field(None, ge=0, description="每日最大请求数")
    daily_cost_limit: float | None = Field(None, ge=0, description="每日最大花费(USD)")
    monthly_token_limit: int | None = Field(None, ge=0, description="每月最大Token数")
    monthly_cost_limit: float | None = Field(None, ge=0, description="每月最大花费(USD)")


class UpdateQuotaConfigRequest(BaseModel):
    daily_token_limit: int | None = Field(None, ge=0)
    daily_request_limit: int | None = Field(None, ge=0)
    daily_cost_limit: float | None = Field(None, ge=0)
    monthly_token_limit: int | None = Field(None, ge=0)
    monthly_cost_limit: float | None = Field(None, ge=0)


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
    if "api_key_encrypted" in result and result["api_key_encrypted"]:
        # Decrypt first to get real prefix/suffix for masking, then mask
        try:
            decrypted = encryption_service.decrypt(result["api_key_encrypted"])
            result["api_key_encrypted"] = _mask_api_key(decrypted)
        except Exception:
            result["api_key_encrypted"] = "****"
    if "secret_key_encrypted" in result and result["secret_key_encrypted"]:
        result["secret_key_encrypted"] = "****"
    return result
