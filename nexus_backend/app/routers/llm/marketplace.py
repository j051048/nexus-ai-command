"""Model marketplace / available-models endpoint and catalog data."""

import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import get_current_user_id
from app.core.config import settings
from app.core.errors import ErrorCode, api_error, api_success

from ._shared import _get_admin_client

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Upstream API-relay providers
# ---------------------------------------------------------------------------


def _get_upstream_providers() -> list[dict]:
    return [
        {"name": "APIYi", "base_url": "https://api.apiyi.com/v1", "api_key": settings.OPENAI_API_KEY},
        *(
            [{"name": "PoloAI", "base_url": settings.AI_FALLBACK_BASE_URL, "api_key": settings.AI_FALLBACK_API_KEY}]
            if settings.AI_FALLBACK_API_KEY and settings.AI_FALLBACK_BASE_URL
            else []
        ),
    ]


# Provider display labels
PROVIDER_LABELS = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "deepseek": "DeepSeek",
    "meta": "Meta",
    "qwen": "阿里通义",
    "zhipu": "智谱",
    "minimax": "MiniMax",
    "moonshot": "月之暗面",
    "yi": "零一万物",
    "baichuan": "百川",
    "stepfun": "阶跃星辰",
    "doubao": "字节豆包",
    "mistral": "Mistral",
    "cohere": "Cohere",
    "unknown": "其他",
}

# Built-in model knowledge base: id -> metadata
# Prices are USD per 1M tokens
MODEL_CATALOG: dict[str, dict] = {
    # ─── OpenAI GPT ───
    "gpt-4o": {
        "name": "GPT-4o",
        "provider": "openai",
        "type": "chat",
        "context": 128000,
        "max_tokens": 16384,
        "tools": True,
        "streaming": True,
        "input_price": 2.5,
        "output_price": 10.0,
        "tags": ["推荐", "多模态"],
    },
    "gpt-4o-2024-11-20": {
        "name": "GPT-4o (Nov 2024)",
        "provider": "openai",
        "type": "chat",
        "context": 128000,
        "max_tokens": 16384,
        "tools": True,
        "streaming": True,
        "input_price": 2.5,
        "output_price": 10.0,
        "tags": ["多模态"],
    },
    "gpt-4o-mini": {
        "name": "GPT-4o Mini",
        "provider": "openai",
        "type": "chat",
        "context": 128000,
        "max_tokens": 16384,
        "tools": True,
        "streaming": True,
        "input_price": 0.15,
        "output_price": 0.6,
        "tags": ["推荐", "高性价比"],
    },
    "gpt-4-turbo": {
        "name": "GPT-4 Turbo",
        "provider": "openai",
        "type": "chat",
        "context": 128000,
        "max_tokens": 4096,
        "tools": True,
        "streaming": True,
        "input_price": 10.0,
        "output_price": 30.0,
        "tags": [],
    },
    "gpt-4-turbo-preview": {
        "name": "GPT-4 Turbo Preview",
        "provider": "openai",
        "type": "chat",
        "context": 128000,
        "max_tokens": 4096,
        "tools": True,
        "streaming": True,
        "input_price": 10.0,
        "output_price": 30.0,
        "tags": [],
    },
    "gpt-4": {
        "name": "GPT-4",
        "provider": "openai",
        "type": "chat",
        "context": 8192,
        "max_tokens": 4096,
        "tools": True,
        "streaming": True,
        "input_price": 30.0,
        "output_price": 60.0,
        "tags": [],
    },
    "gpt-3.5-turbo": {
        "name": "GPT-3.5 Turbo",
        "provider": "openai",
        "type": "chat",
        "context": 16385,
        "max_tokens": 4096,
        "tools": True,
        "streaming": True,
        "input_price": 0.5,
        "output_price": 1.5,
        "tags": ["经济"],
    },
    "o1": {
        "name": "o1",
        "provider": "openai",
        "type": "chat",
        "context": 200000,
        "max_tokens": 100000,
        "tools": False,
        "streaming": True,
        "input_price": 15.0,
        "output_price": 60.0,
        "tags": ["深度推理"],
    },
    "o1-mini": {
        "name": "o1 Mini",
        "provider": "openai",
        "type": "chat",
        "context": 128000,
        "max_tokens": 65536,
        "tools": False,
        "streaming": True,
        "input_price": 3.0,
        "output_price": 12.0,
        "tags": ["推理"],
    },
    "o1-preview": {
        "name": "o1 Preview",
        "provider": "openai",
        "type": "chat",
        "context": 128000,
        "max_tokens": 32768,
        "tools": False,
        "streaming": True,
        "input_price": 15.0,
        "output_price": 60.0,
        "tags": ["推理"],
    },
    "o3-mini": {
        "name": "o3 Mini",
        "provider": "openai",
        "type": "chat",
        "context": 200000,
        "max_tokens": 100000,
        "tools": True,
        "streaming": True,
        "input_price": 1.1,
        "output_price": 4.4,
        "tags": ["推荐", "推理", "高性价比"],
    },
    # ─── Claude ───
    "claude-3-5-sonnet-20241022": {
        "name": "Claude 3.5 Sonnet",
        "provider": "anthropic",
        "type": "chat",
        "context": 200000,
        "max_tokens": 8192,
        "tools": True,
        "streaming": True,
        "input_price": 3.0,
        "output_price": 15.0,
        "tags": ["推荐", "长上下文"],
    },
    "claude-3-5-sonnet-latest": {
        "name": "Claude 3.5 Sonnet (Latest)",
        "provider": "anthropic",
        "type": "chat",
        "context": 200000,
        "max_tokens": 8192,
        "tools": True,
        "streaming": True,
        "input_price": 3.0,
        "output_price": 15.0,
        "tags": ["推荐"],
    },
    "claude-3-5-haiku-20241022": {
        "name": "Claude 3.5 Haiku",
        "provider": "anthropic",
        "type": "chat",
        "context": 200000,
        "max_tokens": 8192,
        "tools": True,
        "streaming": True,
        "input_price": 1.0,
        "output_price": 5.0,
        "tags": ["高性价比"],
    },
    "claude-3-opus-20240229": {
        "name": "Claude 3 Opus",
        "provider": "anthropic",
        "type": "chat",
        "context": 200000,
        "max_tokens": 4096,
        "tools": True,
        "streaming": True,
        "input_price": 15.0,
        "output_price": 75.0,
        "tags": ["最强推理"],
    },
    "claude-3-sonnet-20240229": {
        "name": "Claude 3 Sonnet",
        "provider": "anthropic",
        "type": "chat",
        "context": 200000,
        "max_tokens": 4096,
        "tools": True,
        "streaming": True,
        "input_price": 3.0,
        "output_price": 15.0,
        "tags": [],
    },
    "claude-3-haiku-20240307": {
        "name": "Claude 3 Haiku",
        "provider": "anthropic",
        "type": "chat",
        "context": 200000,
        "max_tokens": 4096,
        "tools": True,
        "streaming": True,
        "input_price": 0.25,
        "output_price": 1.25,
        "tags": ["经济"],
    },
    # ─── Google Gemini ───
    "gemini-2.0-flash": {
        "name": "Gemini 2.0 Flash",
        "provider": "google",
        "type": "chat",
        "context": 1048576,
        "max_tokens": 8192,
        "tools": True,
        "streaming": True,
        "input_price": 0.1,
        "output_price": 0.4,
        "tags": ["推荐", "超长上下文", "高性价比"],
    },
    "gemini-2.0-flash-exp": {
        "name": "Gemini 2.0 Flash Exp",
        "provider": "google",
        "type": "chat",
        "context": 1048576,
        "max_tokens": 8192,
        "tools": True,
        "streaming": True,
        "input_price": 0.1,
        "output_price": 0.4,
        "tags": ["实验"],
    },
    "gemini-1.5-pro": {
        "name": "Gemini 1.5 Pro",
        "provider": "google",
        "type": "chat",
        "context": 2097152,
        "max_tokens": 8192,
        "tools": True,
        "streaming": True,
        "input_price": 1.25,
        "output_price": 5.0,
        "tags": ["超长上下文"],
    },
    "gemini-1.5-flash": {
        "name": "Gemini 1.5 Flash",
        "provider": "google",
        "type": "chat",
        "context": 1048576,
        "max_tokens": 8192,
        "tools": True,
        "streaming": True,
        "input_price": 0.075,
        "output_price": 0.3,
        "tags": ["高性价比"],
    },
    "gemini-2.5-pro-exp-03-25": {
        "name": "Gemini 2.5 Pro",
        "provider": "google",
        "type": "chat",
        "context": 1048576,
        "max_tokens": 65536,
        "tools": True,
        "streaming": True,
        "input_price": 1.25,
        "output_price": 10.0,
        "tags": ["推荐", "最新"],
    },
    # ─── DeepSeek ───
    "deepseek-chat": {
        "name": "DeepSeek V3",
        "provider": "deepseek",
        "type": "chat",
        "context": 64000,
        "max_tokens": 8192,
        "tools": True,
        "streaming": True,
        "input_price": 0.27,
        "output_price": 1.1,
        "tags": ["推荐", "国产", "高性价比"],
    },
    "deepseek-reasoner": {
        "name": "DeepSeek R1",
        "provider": "deepseek",
        "type": "chat",
        "context": 64000,
        "max_tokens": 8192,
        "tools": False,
        "streaming": True,
        "input_price": 0.55,
        "output_price": 2.19,
        "tags": ["推荐", "深度推理", "国产"],
    },
    # ─── Qwen (通义千问) ───
    "qwen-max": {
        "name": "通义千问 Max",
        "provider": "qwen",
        "type": "chat",
        "context": 32000,
        "max_tokens": 8192,
        "tools": True,
        "streaming": True,
        "input_price": 2.0,
        "output_price": 6.0,
        "tags": ["国产"],
    },
    "qwen-plus": {
        "name": "通义千问 Plus",
        "provider": "qwen",
        "type": "chat",
        "context": 131072,
        "max_tokens": 8192,
        "tools": True,
        "streaming": True,
        "input_price": 0.5,
        "output_price": 1.5,
        "tags": ["国产", "高性价比"],
    },
    "qwen-turbo": {
        "name": "通义千问 Turbo",
        "provider": "qwen",
        "type": "chat",
        "context": 131072,
        "max_tokens": 8192,
        "tools": True,
        "streaming": True,
        "input_price": 0.2,
        "output_price": 0.6,
        "tags": ["国产", "经济"],
    },
    "qwen2.5-72b-instruct": {
        "name": "Qwen 2.5 72B",
        "provider": "qwen",
        "type": "chat",
        "context": 131072,
        "max_tokens": 8192,
        "tools": True,
        "streaming": True,
        "input_price": 0.8,
        "output_price": 2.0,
        "tags": ["国产", "开源"],
    },
    # ─── GLM (智谱) ───
    "glm-4-plus": {
        "name": "GLM-4 Plus",
        "provider": "zhipu",
        "type": "chat",
        "context": 128000,
        "max_tokens": 4096,
        "tools": True,
        "streaming": True,
        "input_price": 1.5,
        "output_price": 5.0,
        "tags": ["国产"],
    },
    "glm-4-flash": {
        "name": "GLM-4 Flash",
        "provider": "zhipu",
        "type": "chat",
        "context": 128000,
        "max_tokens": 4096,
        "tools": True,
        "streaming": True,
        "input_price": 0.0,
        "output_price": 0.0,
        "tags": ["国产", "免费"],
    },
    # ─── Moonshot (月之暗面) ───
    "moonshot-v1-128k": {
        "name": "Moonshot v1 128K",
        "provider": "moonshot",
        "type": "chat",
        "context": 128000,
        "max_tokens": 4096,
        "tools": True,
        "streaming": True,
        "input_price": 1.0,
        "output_price": 3.0,
        "tags": ["国产", "长上下文"],
    },
    "moonshot-v1-32k": {
        "name": "Moonshot v1 32K",
        "provider": "moonshot",
        "type": "chat",
        "context": 32000,
        "max_tokens": 4096,
        "tools": True,
        "streaming": True,
        "input_price": 0.5,
        "output_price": 1.5,
        "tags": ["国产"],
    },
    # ─── Mistral ───
    "mistral-large-latest": {
        "name": "Mistral Large",
        "provider": "mistral",
        "type": "chat",
        "context": 128000,
        "max_tokens": 4096,
        "tools": True,
        "streaming": True,
        "input_price": 3.0,
        "output_price": 9.0,
        "tags": [],
    },
    "mistral-small-latest": {
        "name": "Mistral Small",
        "provider": "mistral",
        "type": "chat",
        "context": 128000,
        "max_tokens": 4096,
        "tools": True,
        "streaming": True,
        "input_price": 0.1,
        "output_price": 0.3,
        "tags": ["经济"],
    },
    # ─── Meta Llama ───
    "llama-3.1-405b": {
        "name": "Llama 3.1 405B",
        "provider": "meta",
        "type": "chat",
        "context": 128000,
        "max_tokens": 4096,
        "tools": True,
        "streaming": True,
        "input_price": 3.0,
        "output_price": 3.0,
        "tags": ["开源"],
    },
    "llama-3.1-70b": {
        "name": "Llama 3.1 70B",
        "provider": "meta",
        "type": "chat",
        "context": 128000,
        "max_tokens": 4096,
        "tools": True,
        "streaming": True,
        "input_price": 0.6,
        "output_price": 0.6,
        "tags": ["开源", "高性价比"],
    },
    # ─── Embedding 模型 ───
    "text-embedding-3-large": {
        "name": "Text Embedding 3 Large",
        "provider": "openai",
        "type": "embedding",
        "context": 8191,
        "max_tokens": 0,
        "tools": False,
        "streaming": False,
        "input_price": 0.13,
        "output_price": 0,
        "tags": ["推荐", "向量"],
    },
    "text-embedding-3-small": {
        "name": "Text Embedding 3 Small",
        "provider": "openai",
        "type": "embedding",
        "context": 8191,
        "max_tokens": 0,
        "tools": False,
        "streaming": False,
        "input_price": 0.02,
        "output_price": 0,
        "tags": ["向量", "经济"],
    },
    "text-embedding-ada-002": {
        "name": "Ada v2 Embedding",
        "provider": "openai",
        "type": "embedding",
        "context": 8191,
        "max_tokens": 0,
        "tools": False,
        "streaming": False,
        "input_price": 0.1,
        "output_price": 0,
        "tags": ["向量"],
    },
}


def _infer_provider(model_id: str) -> str:
    """Infer provider from model id string."""
    mid = model_id.lower()
    if mid.startswith(("gpt-", "o1", "o3", "text-embedding", "dall-e", "tts", "whisper")):
        return "openai"
    if "claude" in mid:
        return "anthropic"
    if "gemini" in mid:
        return "google"
    if "deepseek" in mid:
        return "deepseek"
    if "qwen" in mid:
        return "qwen"
    if "glm" in mid:
        return "zhipu"
    if "moonshot" in mid:
        return "moonshot"
    if "mistral" in mid or "mixtral" in mid:
        return "mistral"
    if "llama" in mid:
        return "meta"
    if "yi-" in mid:
        return "yi"
    if "baichuan" in mid:
        return "baichuan"
    if "minimax" in mid or "abab" in mid:
        return "minimax"
    if "doubao" in mid or "skylark" in mid:
        return "doubao"
    if "step" in mid:
        return "stepfun"
    return "unknown"


async def _fetch_models_from_upstream(base_url: str, api_key: str) -> list[str]:
    """Fetch model id list from an OpenAI-compatible /v1/models endpoint."""
    url = f"{base_url.rstrip('/')}/models"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
            resp.raise_for_status()
            data = resp.json()
            # OpenAI format: {"data": [{"id": "model-name", ...}, ...]}
            models_data = data.get("data", [])
            return [m.get("id", "") for m in models_data if m.get("id")]
    except Exception as e:
        logger.warning(f"Failed to fetch models from {base_url}: {e}")
        return []


@router.get("/available-models")
async def list_available_models(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    search: str | None = Query(None, description="搜索模型名称/ID"),
    type_filter: str | None = Query(None, alias="type", description="类型筛选: chat/embedding"),
    tag_filter: str | None = Query(None, alias="tag", description="标签筛选"),
):
    """获取上游转发商可用模型列表（已按分类整理、附带元数据预填充）"""
    try:
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "系统未配置 API Key，无法查询上游模型")

        # 1. Concurrently fetch from all upstream providers (each with its own key)
        providers = _get_upstream_providers()
        tasks = [_fetch_models_from_upstream(p["base_url"], p["api_key"]) for p in providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge & deduplicate
        all_model_ids: set[str] = set()
        upstream_sources: dict[str, list[str]] = {}
        for idx, result in enumerate(results):
            provider_name = providers[idx]["name"]
            if isinstance(result, list):
                for mid in result:
                    all_model_ids.add(mid)
                    upstream_sources.setdefault(mid, []).append(provider_name)

        # 2. Get already-added models from DB
        already_added_codes: set[str] = set()
        client = _get_admin_client()
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        try:
            res = (
                await client.table("llm_model_config")
                .select("model_code")
                .eq("tenant_id", org_id)
                .eq("is_deleted", False)
                .execute()
            )
            already_added_codes = {r["model_code"] for r in (res.data or []) if r.get("model_code")}
        except Exception:
            pass  # Non-critical

        # 3. Build enriched model list
        chat_models: list[dict] = []
        embedding_models: list[dict] = []
        uncategorized_models: list[dict] = []

        for model_id in sorted(all_model_ids):
            catalog_info = MODEL_CATALOG.get(model_id)
            provider = catalog_info["provider"] if catalog_info else _infer_provider(model_id)

            model_entry = {
                "model_id": model_id,
                "name": catalog_info["name"] if catalog_info else model_id,
                "provider": provider,
                "provider_label": PROVIDER_LABELS.get(provider, provider),
                "type": catalog_info["type"] if catalog_info else "chat",
                "context_window": catalog_info["context"] if catalog_info else 0,
                "max_tokens": catalog_info["max_tokens"] if catalog_info else 0,
                "supports_tools": catalog_info["tools"] if catalog_info else False,
                "supports_streaming": catalog_info["streaming"] if catalog_info else True,
                "input_price_per_1m": catalog_info["input_price"] if catalog_info else 0,
                "output_price_per_1m": catalog_info["output_price"] if catalog_info else 0,
                "tags": list(catalog_info["tags"]) if catalog_info else [],
                "already_added": model_id in already_added_codes,
                "has_metadata": catalog_info is not None,
                "available_from": upstream_sources.get(model_id, []),
            }

            # Apply search filter
            if search:
                search_lower = search.lower()
                if search_lower not in model_id.lower() and search_lower not in model_entry["name"].lower():
                    continue

            # Apply tag filter
            if tag_filter and tag_filter not in model_entry["tags"]:
                continue

            # Categorize
            model_type = model_entry["type"]
            if type_filter and model_type != type_filter:
                continue

            if model_type == "embedding":
                embedding_models.append(model_entry)
            elif catalog_info:
                chat_models.append(model_entry)
            else:
                uncategorized_models.append(model_entry)

        # Sort: recommended first, then by name
        def sort_key(m: dict) -> tuple:
            is_recommended = "推荐" in m.get("tags", [])
            return (not is_recommended, not m["has_metadata"], m["name"])

        chat_models.sort(key=sort_key)
        embedding_models.sort(key=sort_key)
        uncategorized_models.sort(key=sort_key)

        categories = []
        if chat_models:
            categories.append({"name": "对话模型", "icon": "💬", "models": chat_models})
        if embedding_models:
            categories.append({"name": "向量模型", "icon": "🔢", "models": embedding_models})
        if uncategorized_models:
            categories.append({"name": "其他模型", "icon": "🔧", "models": uncategorized_models})

        return api_success(
            data={
                "categories": categories,
                "upstream_total": len(all_model_ids),
                "catalog_matched": sum(1 for mid in all_model_ids if mid in MODEL_CATALOG),
                "already_added": len(already_added_codes & all_model_ids),
                "upstream_providers": [p["name"] for p in providers],
            }
        )
    except Exception as e:
        logger.error(f"List available models error: user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "模型市场操作失败")
