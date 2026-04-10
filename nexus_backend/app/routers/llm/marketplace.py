"""LLM 模型市场子路由 — 动态获取上游可用模型 + 硬编码兜底"""

import logging
from collections import defaultdict

import httpx
from fastapi import APIRouter, Query

from app.core.config import settings
from app.core.errors import api_success

from ._shared import (
    AvailableModel,
    AvailableModelsResponse,
    ModelCategory,
    _get_admin_client,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["LLM Marketplace"])

# ---------------------------------------------------------------------------
# Provider 分类规则：根据 model_id 前缀推断供应商
# ---------------------------------------------------------------------------

_PROVIDER_RULES: list[tuple[list[str], str, str, str]] = [
    # (prefixes, provider_code, provider_label, icon)
    (
        [
            "gpt-",
            "o1",
            "o3",
            "o4",
            "chatgpt-",
            "gpt-image",
            "dall-e",
            "text-embedding",
            "text-moderation",
            "omni-moderation",
            "tts-",
            "gpt-oss",
        ],
        "openai",
        "OpenAI",
        "🟢",
    ),
    (["claude-"], "anthropic", "Anthropic", "🟣"),
    (["gemini-", "gemma-", "veo-"], "google", "Google", "🔵"),
    (["deepseek-"], "deepseek", "DeepSeek", "🔷"),
    (["qwen", "qwq-", "qvq-", "tongyi-"], "aliyun", "阿里云/通义", "🟠"),
    (["grok-"], "xai", "xAI", "⚡"),
    (["glm-"], "zhipu", "智谱AI", "🟤"),
    (["kimi-"], "moonshot", "Moonshot", "🌙"),
    (["llama-"], "meta", "Meta", "🦙"),
    (["MiniMax-", "minimax-"], "minimax", "MiniMax", "🅜"),
    (["doubao-", "seed-", "seedream-"], "bytedance", "字节跳动/豆包", "🔥"),
    (["flux-", "sora"], "image", "图像生成", "🎨"),
    (["bge-", "nano-banana"], "embedding", "Embedding/Reranker", "📐"),
    (["step-"], "stepfun", "阶跃星辰", "🪜"),
    (["mimo-"], "xiaomi", "小米", "📱"),
    (["longcat-"], "longcat", "LongCat", "🐱"),
]

# 分类排序（靠前的优先展示）
_CATEGORY_ORDER = [
    "openai",
    "anthropic",
    "google",
    "deepseek",
    "aliyun",
    "xai",
    "zhipu",
    "moonshot",
    "bytedance",
    "meta",
    "minimax",
    "stepfun",
    "xiaomi",
    "longcat",
    "image",
    "embedding",
    "other",
]


def _classify_model(model_id: str) -> tuple[str, str, str]:
    """返回 (provider_code, provider_label, icon)"""
    for prefixes, code, label, icon in _PROVIDER_RULES:
        for prefix in prefixes:
            if model_id.startswith(prefix) or model_id.lower().startswith(
                prefix.lower()
            ):
                return code, label, icon
    return "other", "其他", "🔘"


def _infer_model_type(model_id: str) -> str:
    """推断模型类型"""
    mid = model_id.lower()
    if any(kw in mid for kw in ["embedding", "bge-m3", "bge-reranker"]):
        return "embedding"
    if any(
        kw in mid
        for kw in ["dall-e", "flux-", "gpt-image", "seedream", "sora", "chatgpt-image"]
    ):
        return "image"
    if any(kw in mid for kw in ["tts-"]):
        return "tts"
    if any(kw in mid for kw in ["veo-"]):
        return "video"
    if any(kw in mid for kw in ["moderation", "reranker"]):
        return "tool"
    return "chat"


# ---------------------------------------------------------------------------
# 硬编码元数据：为已知模型补充价格、标签等信息
# ---------------------------------------------------------------------------

_MODEL_METADATA: dict[str, dict] = {
    "gpt-4o": {
        "context_window": 128000,
        "max_tokens": 4096,
        "input_price_per_1m": 2.5,
        "output_price_per_1m": 10.0,
        "tags": ["推荐", "多模态"],
        "supports_tools": True,
    },
    "gpt-4o-mini": {
        "context_window": 128000,
        "max_tokens": 16384,
        "input_price_per_1m": 0.15,
        "output_price_per_1m": 0.6,
        "tags": ["经济", "高性价比"],
        "supports_tools": True,
    },
    "gpt-4.1": {
        "context_window": 1047576,
        "max_tokens": 32768,
        "input_price_per_1m": 2.0,
        "output_price_per_1m": 8.0,
        "tags": ["最新", "长上下文"],
        "supports_tools": True,
    },
    "gpt-4.1-mini": {
        "context_window": 1047576,
        "max_tokens": 32768,
        "input_price_per_1m": 0.4,
        "output_price_per_1m": 1.6,
        "tags": ["经济"],
        "supports_tools": True,
    },
    "gpt-4.1-nano": {
        "context_window": 1047576,
        "max_tokens": 32768,
        "input_price_per_1m": 0.1,
        "output_price_per_1m": 0.4,
        "tags": ["最便宜"],
        "supports_tools": True,
    },
    "o3": {
        "context_window": 200000,
        "max_tokens": 100000,
        "input_price_per_1m": 10.0,
        "output_price_per_1m": 40.0,
        "tags": ["推理", "最强"],
        "supports_tools": True,
    },
    "o3-mini": {
        "context_window": 200000,
        "max_tokens": 100000,
        "input_price_per_1m": 1.1,
        "output_price_per_1m": 4.4,
        "tags": ["推理", "经济"],
        "supports_tools": True,
    },
    "o4-mini": {
        "context_window": 200000,
        "max_tokens": 100000,
        "input_price_per_1m": 1.1,
        "output_price_per_1m": 4.4,
        "tags": ["推理", "最新"],
        "supports_tools": True,
    },
    "claude-sonnet-4-6": {
        "context_window": 200000,
        "max_tokens": 16000,
        "input_price_per_1m": 3.0,
        "output_price_per_1m": 15.0,
        "tags": ["推荐", "编程最强"],
        "supports_tools": True,
    },
    "claude-opus-4-6": {
        "context_window": 200000,
        "max_tokens": 32000,
        "input_price_per_1m": 15.0,
        "output_price_per_1m": 75.0,
        "tags": ["旗舰", "最强推理"],
        "supports_tools": True,
    },
    "claude-haiku-4-5-20251001": {
        "context_window": 200000,
        "max_tokens": 8192,
        "input_price_per_1m": 0.8,
        "output_price_per_1m": 4.0,
        "tags": ["经济", "快速"],
        "supports_tools": True,
    },
    "claude-3-5-sonnet-20240620": {
        "context_window": 200000,
        "max_tokens": 8192,
        "input_price_per_1m": 3.0,
        "output_price_per_1m": 15.0,
        "tags": ["编程"],
        "supports_tools": True,
    },
    "deepseek-chat": {
        "context_window": 64000,
        "max_tokens": 4096,
        "input_price_per_1m": 0.27,
        "output_price_per_1m": 1.1,
        "tags": ["国产", "高性价比", "开源"],
        "supports_tools": True,
    },
    "deepseek-r1": {
        "context_window": 64000,
        "max_tokens": 8192,
        "input_price_per_1m": 0.55,
        "output_price_per_1m": 2.19,
        "tags": ["国产", "推理"],
        "supports_tools": True,
    },
    "gemini-2.5-flash": {
        "context_window": 1048576,
        "max_tokens": 65536,
        "input_price_per_1m": 0.15,
        "output_price_per_1m": 0.6,
        "tags": ["推荐", "超长上下文", "经济"],
        "supports_tools": True,
    },
    "gemini-2.5-pro": {
        "context_window": 1048576,
        "max_tokens": 65536,
        "input_price_per_1m": 1.25,
        "output_price_per_1m": 10.0,
        "tags": ["推理", "长上下文"],
        "supports_tools": True,
    },
    "gemini-3-flash-preview": {
        "context_window": 1048576,
        "max_tokens": 65536,
        "input_price_per_1m": 0.15,
        "output_price_per_1m": 0.6,
        "tags": ["最新", "预览"],
        "supports_tools": True,
    },
    "qwen-max": {
        "context_window": 32000,
        "max_tokens": 4096,
        "input_price_per_1m": 2.0,
        "output_price_per_1m": 6.0,
        "tags": ["国产", "通用强能力"],
        "supports_tools": True,
    },
    "qwen-plus": {
        "context_window": 131072,
        "max_tokens": 8192,
        "input_price_per_1m": 0.8,
        "output_price_per_1m": 2.0,
        "tags": ["国产", "均衡"],
        "supports_tools": True,
    },
    "qwen-turbo": {
        "context_window": 131072,
        "max_tokens": 8192,
        "input_price_per_1m": 0.3,
        "output_price_per_1m": 0.6,
        "tags": ["国产", "经济"],
        "supports_tools": True,
    },
    "grok-3": {
        "context_window": 131072,
        "max_tokens": 8192,
        "input_price_per_1m": 3.0,
        "output_price_per_1m": 15.0,
        "tags": ["推理"],
        "supports_tools": True,
    },
    "grok-4": {
        "context_window": 131072,
        "max_tokens": 8192,
        "input_price_per_1m": 3.0,
        "output_price_per_1m": 15.0,
        "tags": ["最新", "推理"],
        "supports_tools": True,
    },
    "kimi-k2": {
        "context_window": 131072,
        "max_tokens": 8192,
        "input_price_per_1m": 0.6,
        "output_price_per_1m": 2.0,
        "tags": ["国产", "长上下文"],
        "supports_tools": True,
    },
    "glm-4.5": {
        "context_window": 128000,
        "max_tokens": 4096,
        "input_price_per_1m": 0.5,
        "output_price_per_1m": 1.5,
        "tags": ["国产"],
        "supports_tools": True,
    },
    "text-embedding-3-small": {
        "context_window": 8191,
        "max_tokens": 512,
        "input_price_per_1m": 0.02,
        "output_price_per_1m": 0,
        "tags": ["向量", "经济"],
        "supports_tools": False,
        "supports_streaming": False,
    },
    "text-embedding-3-large": {
        "context_window": 8191,
        "max_tokens": 512,
        "input_price_per_1m": 0.13,
        "output_price_per_1m": 0,
        "tags": ["向量", "高精度"],
        "supports_tools": False,
        "supports_streaming": False,
    },
}


def _build_model_from_upstream(model_id: str, owned_by: str) -> dict:
    """从上游 /v1/models 返回的条目构造 AvailableModel dict"""
    provider_code, provider_label, _icon = _classify_model(model_id)
    model_type = _infer_model_type(model_id)
    meta = _MODEL_METADATA.get(model_id, {})

    return {
        "model_id": model_id,
        "name": meta.get("name", model_id),
        "provider": provider_code,
        "provider_label": provider_label,
        "type": model_type,
        "context_window": meta.get("context_window", 8192),
        "max_tokens": meta.get("max_tokens", 4096),
        "supports_tools": meta.get("supports_tools", model_type == "chat"),
        "supports_streaming": meta.get("supports_streaming", model_type == "chat"),
        "input_price_per_1m": meta.get("input_price_per_1m", 0.0),
        "output_price_per_1m": meta.get("output_price_per_1m", 0.0),
        "tags": meta.get("tags", []),
        "has_metadata": model_id in _MODEL_METADATA,
        "available_from": [provider_label],
    }


# ---------------------------------------------------------------------------
# 上游模型列表缓存（避免每次请求都调上游）
# ---------------------------------------------------------------------------

_upstream_cache: dict[str, object] = {"models": None, "ts": 0}
_CACHE_TTL_SECONDS = 600  # 10 分钟


async def _fetch_upstream_models() -> list[dict]:
    """调用上游 /v1/models 获取完整模型列表，带内存缓存"""
    import time

    now = time.time()
    if _upstream_cache["models"] is not None and (now - _upstream_cache["ts"]) < _CACHE_TTL_SECONDS:  # type: ignore[operator]
        return _upstream_cache["models"]  # type: ignore[return-value]

    base_url = settings.AI_BASE_URL.rstrip("/")
    api_key = settings.OPENAI_API_KEY

    if not api_key:
        logger.warning("OPENAI_API_KEY not configured, cannot fetch upstream models")
        return []

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            models = data.get("data", [])
            logger.info(f"Fetched {len(models)} models from upstream {base_url}/models")
            _upstream_cache["models"] = models
            _upstream_cache["ts"] = now
            return models
    except Exception as e:
        logger.warning(f"Failed to fetch upstream models: {e}")
        # 如果缓存还有旧数据，继续使用
        if _upstream_cache["models"] is not None:
            return _upstream_cache["models"]  # type: ignore[return-value]
        return []


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------


@router.get("/available-models")
async def list_available_models(
    search: str | None = Query(None),
    type: str | None = Query(None),
    tag: str | None = Query(None),
):
    """获取可用模型列表(市场) — 动态从上游获取 + 硬编码兜底"""

    # 1. 查询已添加的模型 codes（admin 客户端是异步的，需要 await）
    try:
        client = _get_admin_client()
        added_res = (
            await client.table("llm_model_config").select("model_code").execute()
        )
        added_codes = {r["model_code"] for r in (added_res.data or [])}
    except Exception as e:
        logger.warning(f"Failed to query added models, treating all as unadded: {e}")
        added_codes = set()

    # 2. 从上游获取模型列表
    upstream_models = await _fetch_upstream_models()

    # 3. 构造模型对象，按 provider 分组
    grouped: dict[str, list[dict]] = defaultdict(list)
    provider_icons: dict[str, str] = {}
    provider_labels: dict[str, str] = {}
    all_providers: set[str] = set()

    for um in upstream_models:
        model_id = um.get("id", "")
        owned_by = um.get("owned_by", "")

        # 应用过滤条件
        if search and search.lower() not in model_id.lower():
            continue

        model_data = _build_model_from_upstream(model_id, owned_by)

        if type and type != model_data["type"]:
            continue
        if tag and tag not in model_data["tags"]:
            continue

        provider_code = model_data["provider"]
        _, label, icon = _classify_model(model_id)
        provider_icons[provider_code] = icon
        provider_labels[provider_code] = label
        all_providers.add(label)

        model_data["already_added"] = model_id in added_codes
        grouped[provider_code].append(model_data)

    # 4. 按预定义顺序组装分类
    filtered_categories: list[ModelCategory] = []
    total_count = 0

    for cat_code in _CATEGORY_ORDER:
        models_in_cat = grouped.pop(cat_code, [])
        if not models_in_cat:
            continue
        # 按模型 ID 排序
        models_in_cat.sort(key=lambda m: m["model_id"])
        cat_label = provider_labels.get(cat_code, cat_code)
        cat_icon = provider_icons.get(cat_code, "🔘")

        model_objs = [AvailableModel(**m) for m in models_in_cat]
        total_count += len(model_objs)
        filtered_categories.append(
            ModelCategory(name=cat_label, icon=cat_icon, models=model_objs)
        )

    # 剩余未归类的
    for cat_code, models_in_cat in sorted(grouped.items()):
        if not models_in_cat:
            continue
        models_in_cat.sort(key=lambda m: m["model_id"])
        cat_label = provider_labels.get(cat_code, cat_code)
        cat_icon = provider_icons.get(cat_code, "🔘")
        model_objs = [AvailableModel(**m) for m in models_in_cat]
        total_count += len(model_objs)
        filtered_categories.append(
            ModelCategory(name=cat_label, icon=cat_icon, models=model_objs)
        )

    return api_success(
        data=AvailableModelsResponse(
            categories=filtered_categories,
            upstream_total=len(upstream_models),
            catalog_matched=total_count,
            already_added=len(added_codes),
            upstream_providers=sorted(all_providers),
        )
    )
