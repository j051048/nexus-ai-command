"""LLM 模型市场子路由"""

import logging

from fastapi import APIRouter, Query

from ._shared import AvailableModel, AvailableModelsResponse, ModelCategory, _get_admin_client
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)

router = APIRouter(tags=["LLM Marketplace"])

# 模拟的模型库，目前是硬编码的，后续可改为从数据库或上游获取
MODEL_CATALOG = [
    {
        "name": "旗舰大模型",
        "icon": "🚀",
        "models": [
            {
                "model_id": "gpt-4o",
                "name": "GPT-4o",
                "provider": "openai",
                "provider_label": "OpenAI",
                "type": "chat",
                "context_window": 128000,
                "max_tokens": 4096,
                "supports_tools": True,
                "supports_streaming": True,
                "input_price_per_1m": 5.0,
                "output_price_per_1m": 15.0,
                "tags": ["推荐", "最强推理", "多模态"],
                "available_from": ["OpenAI", "Azure"],
            },
            {
                "model_id": "claude-3-5-sonnet-20240620",
                "name": "Claude 3.5 Sonnet",
                "provider": "anthropic",
                "provider_label": "Anthropic",
                "type": "chat",
                "context_window": 200000,
                "max_tokens": 8192,
                "supports_tools": True,
                "supports_streaming": True,
                "input_price_per_1m": 3.0,
                "output_price_per_1m": 15.0,
                "tags": ["推荐", "推理", "编程最强"],
                "available_from": ["AWS Bedrock", "GCP Vertex AI"],
            },
        ],
    },
    {
        "name": "国产自研大模型",
        "icon": "🇨🇳",
        "models": [
            {
                "model_id": "deepseek-chat",
                "name": "DeepSeek V3",
                "provider": "deepseek",
                "provider_label": "DeepSeek",
                "type": "chat",
                "context_window": 64000,
                "max_tokens": 4096,
                "supports_tools": True,
                "supports_streaming": True,
                "input_price_per_1m": 1.0,
                "output_price_per_1m": 2.0,
                "tags": ["国产", "高性价比", "开源"],
                "available_from": ["DeepSeek API"],
            },
            {
                "model_id": "qwen-max",
                "name": "通义千问 Max",
                "provider": "aliyun",
                "provider_label": "阿里云",
                "type": "chat",
                "context_window": 32000,
                "max_tokens": 4096,
                "supports_tools": True,
                "supports_streaming": True,
                "input_price_per_1m": 20.0,
                "output_price_per_1m": 60.0,
                "tags": ["国产", "通用强能力"],
                "available_from": ["DashScope"],
            },
        ],
    },
    {
        "name": "向量与轻量模型",
        "icon": "⚡",
        "models": [
            {
                "model_id": "text-embedding-3-small",
                "name": "OpenAI Embedding 3 Small",
                "provider": "openai",
                "provider_label": "OpenAI",
                "type": "embedding",
                "context_window": 8191,
                "max_tokens": 512,
                "supports_tools": False,
                "supports_streaming": False,
                "input_price_per_1m": 0.02,
                "output_price_per_1m": 0,
                "tags": ["向量", "经济"],
                "available_from": ["OpenAI"],
            },
            {
                "model_id": "gpt-4o-mini",
                "name": "GPT-4o Mini",
                "provider": "openai",
                "provider_label": "OpenAI",
                "type": "chat",
                "context_window": 128000,
                "max_tokens": 4096,
                "supports_tools": True,
                "supports_streaming": True,
                "input_price_per_1m": 0.15,
                "output_price_per_1m": 0.6,
                "tags": ["经济", "高性价比", "最新的"],
                "available_from": ["OpenAI"],
            },
        ],
    },
]


@router.get("/available-models")
async def list_available_models(
    search: str | None = Query(None),
    type: str | None = Query(None),
    tag: str | None = Query(None),
):
    """获取可用模型列表(市场)"""
    try:
        client = _get_admin_client()
        # 同步调用放在 try 中，避免阻塞时未捕获异常
        added_res = client.table("llm_model_config").select("model_code").execute()
        added_codes = {r["model_code"] for r in (added_res.data or [])}
    except Exception as e:
        logger.warning(f"Failed to query added models, treating all as unadded: {e}")
        added_codes = set()

    filtered_categories = []
    total_count = 0

    for cat in MODEL_CATALOG:
        matched_models = []
        for m in cat["models"]:
            # 应用过滤条件
            if search and search.lower() not in m["name"].lower() and search.lower() not in m["model_id"].lower():
                continue
            if type and type != m["type"]:
                continue
            if tag and tag not in m["tags"]:
                continue

            # 构建返回的模型对象
            model_obj = AvailableModel(
                **m,
                already_added=m["model_id"] in added_codes,
            )
            matched_models.append(model_obj)
            total_count += 1

        if matched_models:
            filtered_categories.append(
                ModelCategory(
                    name=cat["name"],
                    icon=cat["icon"],
                    models=matched_models,
                )
            )

    return api_success(data=AvailableModelsResponse(
        categories=filtered_categories,
        upstream_total=total_count,
        catalog_matched=total_count,
        already_added=len(added_codes),
        upstream_providers=["OpenAI", "Anthropic", "DeepSeek", "Aliyun"],
    ))
