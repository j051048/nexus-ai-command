"""
LLM Gateway - Model Resolution Module

Handles model config loading, schedule rule resolution, circuit breaker
integration, and context window auto-upgrade logic.
"""

import logging
import time

from app.core.database import supabase
from app.services.encryption_service import encryption_service
from app.services.llm_adapters.base import BaseModelAdapter, ModelConfig
from app.services.llm_adapters.registry import get_adapter
from app.services.llm_circuit_breaker import circuit_breaker_manager
from app.services.token_service import token_counter

logger = logging.getLogger(__name__)


class ModelResolutionMixin:
    """
    Mixin providing model config loading, schedule rule resolution,
    circuit breaker checks, and context window upgrade logic.

    Requires:
        self._model_cache: dict[str, tuple[ModelConfig, float]]
        self._schedule_cache: dict[str, tuple[dict, float]]
        self._CACHE_TTL: int
    """

    async def _load_model_config(self, model_code: str, org_id: str) -> ModelConfig | None:
        """
        Load a model configuration from the llm_model_config table.

        Results are cached for _CACHE_TTL seconds.  The encrypted api_key
        stored in the database is decrypted before being placed into the
        returned ModelConfig.

        Returns None if the model is not found or the database is
        unavailable.
        """
        cache_key = f"{org_id}:{model_code}"
        now = time.time()

        # Check cache
        if cache_key in self._model_cache:
            config, loaded_at = self._model_cache[cache_key]
            if now - loaded_at < self._CACHE_TTL:
                return config

        if not supabase:
            logger.warning("Database not available - cannot load model config")
            return None

        try:
            # Try tenant-specific first, then fall back to global defaults
            rows = []

            # 1. Try org-specific config
            if org_id and org_id != "default":
                res = (
                    await supabase.table("llm_model_config")
                    .select("*")
                    .eq("model_code", model_code)
                    .eq("tenant_id", org_id)
                    .eq("status", "enabled")
                    .eq("is_deleted", False)
                    .execute()
                )
                rows = res.data or []

            # 2. Fall back to global defaults (tenant_id IS NULL = global config)
            if not rows:
                res = (
                    await supabase.table("llm_model_config")
                    .select("*")
                    .eq("model_code", model_code)
                    .is_("tenant_id", "null")
                    .eq("status", "enabled")
                    .eq("is_deleted", False)
                    .execute()
                )
                rows = res.data or []

            if not rows:
                logger.warning(f"No config found for model={model_code}, org={org_id}")
                return None

            row = rows[0]

            # Decrypt the API key
            api_key = row.get("api_key", "")
            if api_key:
                try:
                    api_key = encryption_service.decrypt(api_key)
                except Exception:
                    logger.debug(f"API key for {model_code} appears unencrypted, using as-is")

            config = ModelConfig(
                model_code=row.get("model_code", model_code),
                model_name=row.get("model_name", model_code),
                provider_type=row.get("provider_type", "openai_compatible"),
                api_key=api_key,
                api_base_url=row.get("base_url", ""),
                model_id=str(row.get("id", "")),
                context_window=row.get("context_window", 4096),
                max_tokens=row.get("max_output_tokens") or row.get("max_tokens", 4096),
                supports_tools=row.get("supports_tools", False),
                default_temperature=row.get("default_temperature", 0.7),
            )

            self._model_cache[cache_key] = (config, now)
            return config

        except Exception as e:
            logger.error(f"Error loading model config for {model_code}: {e}", exc_info=True)
            return None

    async def _resolve_model(
        self, scene_code: str, agent_code: str, org_id: str, complexity_tier: str | None = None
    ) -> str | None:
        """
        Look up the llm_schedule_rule table to find the model assigned
        to a given scene + agent combination, optionally filtered by complexity.

        Resolution priority:
        1. Exact match (scene + agent + complexity_tier)
        2. Complexity wildcard (scene + agent + complexity_tier IS NULL)
        3. Scene-level default (agent_code = '*')
        4. Org-level default (scene_code = '*')

        Returns the primary model_code.  If the primary model's circuit
        breaker is open, returns the backup_model_code instead.
        Returns None when no matching rule exists.
        """
        cache_key = f"{org_id}:{scene_code}:{agent_code}:{complexity_tier or '_'}"
        now = time.time()

        # Check cache
        if cache_key in self._schedule_cache:
            rule, loaded_at = self._schedule_cache[cache_key]
            if now - loaded_at < self._CACHE_TTL:
                return self._pick_healthy_model(rule)

        if not supabase:
            logger.warning("Database not available - cannot resolve model schedule")
            return None

        try:
            # Try tenant-specific first, then fall back to global (NULL tenant_id)
            for tid in [org_id, None]:
                rows = []

                # P2-9: Try exact match with complexity_tier first
                if complexity_tier:
                    q = (
                        supabase.table("llm_schedule_rule")
                        .select("*")
                        .eq("scene_code", scene_code)
                        .eq("agent_code", agent_code)
                        .eq("complexity_tier", complexity_tier)
                    )
                    q = q.eq("tenant_id", tid) if tid else q.is_("tenant_id", "null")
                    res = await q.execute()
                    rows = res.data or []

                # Fallback: complexity wildcard (NULL complexity_tier)
                if not rows:
                    q = (
                        supabase.table("llm_schedule_rule")
                        .select("*")
                        .eq("scene_code", scene_code)
                        .eq("agent_code", agent_code)
                        .is_("complexity_tier", "null")
                    )
                    q = q.eq("tenant_id", tid) if tid else q.is_("tenant_id", "null")
                    res = await q.execute()
                    rows = res.data or []

                # Fallback: scene + agent without complexity filter
                if not rows:
                    q = (
                        supabase.table("llm_schedule_rule")
                        .select("*")
                        .eq("scene_code", scene_code)
                        .eq("agent_code", agent_code)
                    )
                    q = q.eq("tenant_id", tid) if tid else q.is_("tenant_id", "null")
                    res = await q.execute()
                    rows = res.data or []

                # Fallback: scene-level default (agent_code = '*' or empty)
                if not rows:
                    q = (
                        supabase.table("llm_schedule_rule")
                        .select("*")
                        .eq("scene_code", scene_code)
                        .in_("agent_code", ["*", ""])
                    )
                    q = q.eq("tenant_id", tid) if tid else q.is_("tenant_id", "null")
                    res = await q.execute()
                    rows = res.data or []

                # Fallback: org-level default (scene_code = '*')
                if not rows:
                    q = (
                        supabase.table("llm_schedule_rule")
                        .select("*")
                        .in_("scene_code", ["*", ""])
                    )
                    q = q.eq("tenant_id", tid) if tid else q.is_("tenant_id", "null")
                    res = await q.execute()
                    rows = res.data or []

                if rows:
                    break

            if not rows:
                logger.warning(f"No schedule rule found for scene={scene_code}, agent={agent_code}, org={org_id}")
                return None

            rule = rows[0]

            # Resolve model_id -> model_code when code is missing
            await self._fill_model_codes(rule)

            self._schedule_cache[cache_key] = (rule, now)
            return self._pick_healthy_model(rule)

        except Exception as e:
            logger.error(
                f"Error resolving model for scene={scene_code}, agent={agent_code}, org={org_id}: {e}",
                exc_info=True,
            )
            return None

    async def _fill_model_codes(self, rule: dict) -> None:
        """
        If a schedule rule has *_model_id but not *_model_code, look up the
        model_code from llm_model_config by ID.  Mutates the rule dict in place.
        """
        if not supabase:
            return

        for code_key, id_key in [
            ("primary_model_code", "primary_model_id"),
            ("backup_model_code", "backup_model_id"),
        ]:
            if not rule.get(code_key) and rule.get(id_key):
                try:
                    res = (
                        await supabase.table("llm_model_config")
                        .select("model_code")
                        .eq("id", rule[id_key])
                        .maybe_single()
                        .execute()
                    )
                    if res and res.data and res.data.get("model_code"):
                        rule[code_key] = res.data["model_code"]
                        logger.info(f"Resolved {id_key}={rule[id_key]} -> {code_key}={rule[code_key]}")
                    else:
                        logger.warning(f"No model_code found for {id_key}={rule[id_key]}")
                except Exception as e:
                    logger.warning(f"Failed to resolve {id_key}={rule[id_key]}: {e}")

    def _pick_healthy_model(self, rule: dict) -> str | None:
        """
        From a schedule rule row, return the primary model if its circuit
        breaker allows requests; otherwise return the backup model.
        """
        primary = rule.get("primary_model_code") or None
        backup = rule.get("backup_model_code") or None

        if primary and circuit_breaker_manager.is_allowed(primary):
            return primary

        if primary:
            logger.warning(f"Primary model '{primary}' circuit is open, attempting backup model '{backup}'")

        if backup and circuit_breaker_manager.is_allowed(backup):
            return backup

        if backup:
            logger.error(f"Both primary '{primary}' and backup '{backup}' circuits are open")

        # Return primary anyway as last resort
        return primary

    async def _find_larger_context_model(
        self, current_model_code: str, org_id: str, required_tokens: int
    ) -> str | None:
        """Find an enabled chat model with a larger context window that fits required_tokens."""
        if not supabase:
            return None
        try:
            current_config = await self._load_model_config(current_model_code, org_id)
            if not current_config:
                return None
            min_window = int(required_tokens / 0.8) + 1
            res = (
                await supabase.table("llm_model_config")
                .select("model_code, context_window, provider_type")
                .eq("status", "enabled")
                .eq("is_deleted", False)
                .eq("model_type", "chat")
                .gte("context_window", min_window)
                .neq("model_code", current_model_code)
                .order("context_window", desc=False)
                .limit(5)
                .execute()
            )
            candidates = res.data or []
            # Prefer same provider
            same_provider = [c for c in candidates if c.get("provider_type") == current_config.provider_type]
            if same_provider:
                return same_provider[0]["model_code"]
            if candidates:
                return candidates[0]["model_code"]
            return None
        except Exception as e:
            logger.warning(f"Failed to find larger context model: {e}")
            return None

    async def _maybe_upgrade_for_context(
        self,
        model_code: str,
        org_id: str,
        config: ModelConfig,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> tuple[str, ModelConfig]:
        """
        Check if the current model's context window is too small for the
        prompt and auto-upgrade to a larger model if available.
        """
        try:
            estimated_tokens = token_counter.estimate_prompt_tokens(
                system_prompt, messages, tools, config.model_code
            )
            if estimated_tokens > config.context_window * 0.8:
                larger = await self._find_larger_context_model(model_code, org_id, estimated_tokens)
                if larger:
                    larger_config = await self._load_model_config(larger, org_id)
                    if larger_config:
                        logger.info(
                            f"Auto-upgrading from {model_code} (ctx={config.context_window}) "
                            f"to {larger} (ctx={larger_config.context_window}) "
                            f"for {estimated_tokens} estimated tokens"
                        )
                        return larger, larger_config
        except Exception as e:
            logger.debug(f"Context upgrade check failed (non-fatal): {e}")
        return model_code, config

    async def _create_adapter(
        self, model_code: str, org_id: str
    ) -> tuple[BaseModelAdapter, ModelConfig] | tuple[None, None]:
        """Load config and instantiate the appropriate adapter."""
        config = await self._load_model_config(model_code, org_id)
        if not config:
            return None, None

        try:
            adapter = get_adapter(config.provider_type, config)
            return adapter, config
        except ValueError as e:
            logger.error(f"Failed to create adapter for {model_code}: {e}")
            return None, None

    async def _get_backup_model(
        self,
        scene_code: str,
        agent_code: str,
        org_id: str,
        exclude: str,
    ) -> str | None:
        """
        Look up the backup model from the cached schedule rule,
        excluding the already-failed model.
        """
        prefix = f"{org_id}:{scene_code}:{agent_code}:"
        for key, (rule, _) in self._schedule_cache.items():
            if key.startswith(prefix):
                backup = rule.get("backup_model_code") or None
                if backup and backup != exclude and circuit_breaker_manager.is_allowed(backup):
                    return backup
        return None

    def invalidate_cache(self, org_id: str | None = None) -> None:
        """
        Clear model config and schedule rule caches.

        If org_id is provided, only entries for that org are removed.
        If org_id is None, all caches are cleared.
        """
        if org_id is None:
            self._model_cache.clear()
            self._schedule_cache.clear()
            logger.info("All LLM gateway caches invalidated")
        else:
            model_keys = [k for k in self._model_cache if k.startswith(f"{org_id}:")]
            schedule_keys = [k for k in self._schedule_cache if k.startswith(f"{org_id}:")]
            for k in model_keys:
                del self._model_cache[k]
            for k in schedule_keys:
                del self._schedule_cache[k]
            logger.info(
                f"LLM gateway caches invalidated for org={org_id} "
                f"({len(model_keys)} model, "
                f"{len(schedule_keys)} schedule entries)"
            )
