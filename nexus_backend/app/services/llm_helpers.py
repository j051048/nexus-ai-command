"""
LLM Helpers - Bridge between existing code and the unified LLM Gateway.

Provides convenience wrappers so that existing code (LangChain-based agents,
direct OpenAI SDK users) can transparently benefit from the gateway's model
resolution, quota management, circuit breaking, and failover capabilities.
"""

import logging
import os
import re

from app.core.config import settings

logger = logging.getLogger(__name__)

# Model codes too weak for power/flagship complexity tasks.
# Matched as whole "segments" delimited by `-` to avoid false positives
# (e.g. "mini" must NOT match "ge-mini" in "gemini").
_WEAK_MODEL_PATTERNS = {"mini", "flash", "turbo-mini", "haiku", "lite", "nano", "small", "instant"}
_WEAK_MODEL_CODES = {"deepseek-chat", "qwen-plus-latest", "qwen-turbo", "glm-4-flash", "yi-lightning"}

# Models that contain weak-sounding substrings but are actually capable.
# Exact matches checked first, then prefix patterns for version resilience.
_STRONG_MODEL_OVERRIDES = {
    "gemini-3-flash-preview",
    "gemini-3.1-flash-preview",
    "gemini-2.0-flash",
    "gemini-2.5-flash-preview-05-20",
    "claude-3.5-sonnet",  # contains no weak pattern but guard future renames
}

# Prefix patterns: any model starting with these is considered strong
# despite containing weak substrings (e.g. "flash").
# This avoids needing to update the whitelist for every new version.
_STRONG_MODEL_PREFIXES = (
    "gemini-2.0-flash",  # gemini-2.0-flash, gemini-2.0-flash-001, ...
    "gemini-2.5-flash",  # gemini-2.5-flash-preview-*, ...
    "gemini-3-flash",  # gemini-3-flash-preview, ...
    "gemini-3.1-flash",  # gemini-3.1-flash-preview, ...
)

# Pre-compiled regex: match weak patterns as whole segments between `-` or
# at string boundaries.  E.g. "mini" matches "gpt-4o-mini" but NOT "gemini".
_WEAK_SEGMENT_RE = re.compile(r"(?:^|-)(" + "|".join(re.escape(p) for p in _WEAK_MODEL_PATTERNS) + r")(?:-|$)")


def is_weak_model(model_name: str) -> bool:
    """Check if a model is too weak for power/flagship tier tasks.

    Covers common weak model families: mini, flash, turbo-mini, haiku,
    lite, nano, small, instant, and specific model codes known to be
    economy-tier.  Strong model overrides (exact or prefix) are
    whitelisted to avoid false positives (e.g. gemini-2.0-flash is
    capable despite 'flash').

    Weak patterns are matched as whole `-`-delimited segments to prevent
    false positives like "gemini" matching "mini".
    """
    if not model_name:
        return True
    if model_name in _STRONG_MODEL_OVERRIDES:
        return False
    # Prefix-based whitelist for version resilience
    if any(model_name.startswith(p) for p in _STRONG_MODEL_PREFIXES):
        return False
    lower = model_name.lower()
    if _WEAK_SEGMENT_RE.search(lower):
        return True
    return model_name in _WEAK_MODEL_CODES


# ─── Auto Tier Detection ─────────────────────────────────────────────────────

# Scenes that always require higher-tier models
_POWER_SCENES = {"tender_analysis", "content_generation", "contract_review", "data_analysis"}
_FLAGSHIP_SCENES = {"task_decompose", "compliance_check"}


def auto_detect_tier(
    messages: list[dict] | None = None,
    tools_count: int = 0,
    scene_code: str = "",
    iteration: int = 0,
) -> str:
    """Auto-detect complexity tier based on request characteristics.

    Pure rule-based (no LLM call), used to optimize model selection
    when the router hasn't explicitly set complexity.

    Returns: economy | balanced | power | flagship
    """
    # Flagship: multi-round complex reasoning or critical scenes
    if iteration > 2 or scene_code in _FLAGSHIP_SCENES:
        return "flagship"

    # Power: many tools, long context, or complex scenes
    if tools_count > 3 or scene_code in _POWER_SCENES:
        return "power"

    # Estimate message length
    total_chars = 0
    if messages:
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)

    # Economy: short messages, no tools, first iteration
    if total_chars < 500 and tools_count == 0 and iteration == 0:
        return "economy"

    # Balanced: default for moderate workloads
    return "balanced"


def _build_tier_fallback(tier: str, scene_code: str = "") -> dict | None:
    """Build tier-specific fallback config from YAML config file.

    Used when the LLM Gateway has no DB schedule rules configured.
    Loads from config/models.yaml with env variable overrides.
    """
    from app.core.model_config import get_model_config

    try:
        config = get_model_config(tier=tier, scene_code=scene_code)
        if not config:
            return None

        # 根据 provider 选择正确的 API Key 和 Base URL
        provider = config.get("provider", "openai").lower()
        if provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY") or getattr(settings, "ANTHROPIC_API_KEY", "")
            base_url = os.getenv("ANTHROPIC_BASE_URL") or getattr(
                settings, "ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"
            )
        else:  # openai or compatible
            api_key = os.getenv("OPENAI_API_KEY") or settings.OPENAI_API_KEY
            base_url = os.getenv("AI_BASE_URL") or getattr(settings, "AI_BASE_URL", "https://api.openai.com/v1")

        return {
            "api_key": api_key,
            "base_url": base_url,
            "model": config.get("model", "gpt-4o-mini"),
            "temperature": config.get("temperature", 0.7),
            "timeout": config.get("timeout", 60.0),
            "supports_tools": config.get("supports_tools", True),
            "context_window": config.get("context_window"),
        }
    except Exception as e:
        logger.error(f"Failed to load model config: {e}")
        return None


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

                resolved_model = config.model_id or config.model_code

                # Guard: if power/flagship tier but Gateway returned a weak model,
                # fall through to tier-aware hardcoded fallback instead.
                if complexity_tier in ("power", "flagship") and is_weak_model(resolved_model):
                    logger.info(
                        "Gateway returned weak model %s for %s tier, using tier fallback",
                        resolved_model,
                        complexity_tier,
                    )
                else:
                    return {
                        "api_key": config.api_key,
                        "base_url": config.api_base_url,
                        "model": resolved_model,
                        "temperature": config.default_temperature,
                        "timeout": config.timeout_ms / 1000,
                        "supports_tools": config.supports_tools,
                        "context_window": config.context_window,
                    }
    except Exception as e:
        logger.error("Gateway model resolution failed, using fallback: %s", e)

    # Tier-aware hardcoded fallback
    if complexity_tier:
        tier_fb = _build_tier_fallback(complexity_tier, scene_code)
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
    Falls back to YAML config + settings.
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
        logger.error("Gateway embedding resolution failed, using fallback: %s", e)

    # Fallback to YAML config
    from app.core.model_config import get_embedding_config

    yaml_config = get_embedding_config()
    return {
        "api_key": os.getenv("OPENAI_API_KEY") or settings.OPENAI_API_KEY,
        "base_url": os.getenv("AI_BASE_URL") or getattr(settings, "AI_BASE_URL", "https://api.openai.com/v1"),
        "model": yaml_config.get("model", "text-embedding-3-large"),
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
