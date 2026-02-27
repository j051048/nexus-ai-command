"""
LLM Helpers - Bridge between existing code and the unified LLM Gateway.

Provides convenience wrappers so that existing code (LangChain-based agents,
direct OpenAI SDK users) can transparently benefit from the gateway's model
resolution, quota management, circuit breaking, and failover capabilities.
"""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


async def resolve_model_config(
    org_id: str = "default",
    scene_code: str = "",
    agent_code: str = "",
) -> dict:
    """
    Resolve model configuration via the LLM Gateway.

    Returns a dict with keys: api_key, base_url, model, temperature, timeout, supports_tools
    Falls back to settings if gateway resolution fails.
    """
    try:
        from app.services.llm_gateway_service import llm_gateway

        # Always try gateway resolution — use wildcards when scene/agent not specified
        resolved_scene = scene_code or "*"
        resolved_agent = agent_code or "*"
        model_code = await llm_gateway._resolve_model(resolved_scene, resolved_agent, org_id)
        if model_code:
            config = await llm_gateway._load_model_config(model_code, org_id)
            if config:
                return {
                    "api_key": config.api_key,
                    "base_url": config.api_base_url,
                    "model": config.model_id or config.model_code,
                    "temperature": config.default_temperature,
                    "timeout": config.timeout_ms / 1000,
                    "supports_tools": config.supports_tools,
                }
    except Exception as e:
        logger.debug("Gateway model resolution failed, using fallback: %s", e)

    # Fallback to existing settings
    return {
        "api_key": settings.OPENAI_API_KEY,
        "base_url": getattr(settings, "AI_BASE_URL", "https://api.openai.com/v1"),
        "model": getattr(settings, "AI_DEFAULT_MODEL", "gpt-4o"),
        "temperature": 0.7,
        "timeout": 60.0,
        "supports_tools": True,
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
