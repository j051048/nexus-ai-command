"""
LLM Helpers - Bridge between existing code and the unified LLM Gateway.

Provides convenience wrappers so that existing code (LangChain-based agents,
direct OpenAI SDK users) can transparently benefit from the gateway's model
resolution, quota management, circuit breaking, and failover capabilities.
"""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_tier_fallback(tier: str) -> dict | None:
    """Build tier-specific fallback config from env settings.

    Used when the LLM Gateway has no DB schedule rules configured.
    Maps 4 complexity tiers to different model/temperature/timeout combos.
    """
    _tiers = {
        #            (settings attr,      default model,  temp, timeout, tools)
        "economy": ("AI_MINI_MODEL", "gpt-4o-mini", 0.3, 30.0, False),
        "balanced": ("AI_MINI_MODEL", "gpt-4o-mini", 0.5, 45.0, True),
        "power": ("AI_DEFAULT_MODEL", "gpt-4o", 0.7, 60.0, True),
        "flagship": ("AI_DEFAULT_MODEL", "gpt-4o", 0.5, 90.0, True),
    }
    if tier not in _tiers:
        return None
    attr, default_model, temp, timeout, tools = _tiers[tier]
    return {
        "api_key": settings.OPENAI_API_KEY,
        "base_url": getattr(settings, "AI_BASE_URL", "https://api.openai.com/v1"),
        "model": getattr(settings, attr, default_model),
        "temperature": temp,
        "timeout": timeout,
        "supports_tools": tools,
        "context_window": None,
    }


async def resolve_model_config(
    org_id: str = "default",
    scene_code: str = "",
    agent_code: str = "",
    complexity_tier: str | None = None,
    messages: list[dict] | None = None,
    system_prompt: str = "",
    tools: list[dict] | None = None,
) -> dict:
    """
    Resolve model configuration via the LLM Gateway.

    Returns a dict with keys: api_key, base_url, model, temperature, timeout,
    supports_tools, context_window.
    Falls back to tier-aware hardcoded map when gateway resolution fails.

    When *messages* is provided, estimates prompt tokens and auto-upgrades
    to a larger context model if the current one's window is insufficient.
    """
    try:
        from app.services.llm_gateway_service import llm_gateway

        # Always try gateway resolution — use wildcards when scene/agent not specified
        resolved_scene = scene_code or "*"
        resolved_agent = agent_code or "*"
        model_code = await llm_gateway._resolve_model(
            resolved_scene, resolved_agent, org_id, complexity_tier=complexity_tier
        )
        if model_code:
            config = await llm_gateway._load_model_config(model_code, org_id)
            if config:
                # Token-based context window upgrade
                if messages and config.context_window:
                    model_code, config = await llm_gateway._maybe_upgrade_for_context(
                        model_code, org_id, config, system_prompt, messages, tools
                    )

                return {
                    "api_key": config.api_key,
                    "base_url": config.api_base_url,
                    "model": config.model_id or config.model_code,
                    "temperature": config.default_temperature,
                    "timeout": config.timeout_ms / 1000,
                    "supports_tools": config.supports_tools,
                    "context_window": config.context_window,
                }
    except Exception as e:
        logger.debug("Gateway model resolution failed, using fallback: %s", e)

    # Tier-aware hardcoded fallback
    if complexity_tier:
        tier_fb = _build_tier_fallback(complexity_tier)
        if tier_fb:
            return tier_fb

    # Generic fallback (no tier specified)
    return {
        "api_key": settings.OPENAI_API_KEY,
        "base_url": getattr(settings, "AI_BASE_URL", "https://api.openai.com/v1"),
        "model": getattr(settings, "AI_DEFAULT_MODEL", "gpt-4o"),
        "temperature": 0.7,
        "timeout": 60.0,
        "supports_tools": True,
        "context_window": None,
    }


async def resolve_embedding_config(org_id: str = "default") -> dict:
    """
    Resolve embedding model configuration via the LLM Gateway.

    Returns a dict with keys: api_key, base_url, model
    Falls back to settings + default text-embedding-3-small.
    """
    try:
        from app.core.database import supabase
        from app.services.llm_gateway_service import llm_gateway

        # Try to find an embedding model in the schedule rules
        # Load the default embedding model config directly from DB
        if supabase:
            res = (
                await supabase.table("llm_model_config")
                .select("model_code")
                .eq("model_type", "embedding")
                .eq("status", "enabled")
                .eq("is_deleted", False)
                .limit(1)
                .execute()
            )
            if res.data:
                model_code = res.data[0]["model_code"]
                config = await llm_gateway._load_model_config(model_code, org_id)
                if config:
                    return {
                        "api_key": config.api_key,
                        "base_url": config.api_base_url,
                        "model": config.model_id or config.model_code,
                    }
    except Exception as e:
        logger.debug("Gateway embedding resolution failed, using fallback: %s", e)

    # Fallback
    return {
        "api_key": settings.OPENAI_API_KEY,
        "base_url": getattr(settings, "AI_BASE_URL", "https://api.openai.com/v1"),
        "model": "text-embedding-3-small",
    }


def get_langchain_llm_sync(
    api_key: str,
    base_url: str,
    model: str,
    temperature: float = 0.7,
    streaming: bool = False,
    timeout: float = 60.0,
):
    """Create a LangChain ChatOpenAI instance from resolved config."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        streaming=streaming,
        timeout=timeout,
    )
