"""
VMD Role Registry — loads role configs from DB (vmd_agent_config) or fallback code defaults.

Provides:
- get_role_config(agent_code, tenant_id=None) -> RoleConfig
- get_all_roles() -> list[RoleConfig]
- ROLE_REGISTRY: dict[str, RoleConfig]
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ─── RoleConfig Dataclass ────────────────────────────────────────────────────


@dataclass
class RoleConfig:
    """Configuration for a single VMD agent role."""

    agent_code: str
    agent_name: str
    system_prompt: str
    tool_whitelist: list[str] = field(default_factory=list)
    scene_codes: list[str] = field(default_factory=list)
    recommended_model_tier: str = "medium"  # "low", "medium", "high"

    def get_tool_schemas(self) -> list[dict]:
        """Return OpenAI-format tool schemas filtered by this role's whitelist."""
        from app.tools import get_all_tools_schema

        if not self.tool_whitelist:
            return get_all_tools_schema()  # No whitelist = all tools

        all_schemas = get_all_tools_schema()
        return [s for s in all_schemas if s["function"]["name"] in self.tool_whitelist]


# ─── Fallback Role Module Map ────────────────────────────────────────────────

# Maps agent_code -> module path under app.agent.roles
_ROLE_MODULES: dict[str, str] = {
    "director_agent": "app.agent.roles.director",
    "content_agent": "app.agent.roles.content",
    "design_agent": "app.agent.roles.design",
    "media_agent": "app.agent.roles.media",
    "clue_agent": "app.agent.roles.clue",
    "sales_agent": "app.agent.roles.sales",
    "synergy_agent": "app.agent.roles.synergy",
    "operation_agent": "app.agent.roles.operation",
    "pr_agent": "app.agent.roles.pr",
    "compliance_agent": "app.agent.roles.compliance_role",
}


def _load_role_from_module(module_path: str) -> RoleConfig:
    """Import a role module and build a RoleConfig from its constants."""
    mod = importlib.import_module(module_path)
    return RoleConfig(
        agent_code=mod.AGENT_CODE,
        agent_name=mod.AGENT_NAME,
        system_prompt=mod.SYSTEM_PROMPT,
        tool_whitelist=getattr(mod, "TOOL_WHITELIST", []),
        scene_codes=getattr(mod, "SCENE_CODES", []),
        recommended_model_tier=getattr(mod, "RECOMMENDED_MODEL_TIER", "medium"),
    )


# ─── DB-backed Config Loader ────────────────────────────────────────────────


async def _load_role_from_db(agent_code: str, tenant_id: str | None = None) -> RoleConfig | None:
    """
    Attempt to load a role config from the vmd_agent_config table.

    Returns None if the table does not exist or the record is not found.
    DB schema expected:
        vmd_agent_config(
            agent_code text PK,
            agent_name text,
            system_prompt text,
            tool_whitelist jsonb,
            scene_codes jsonb,
            recommended_model_tier text,
            tenant_id text,
            is_active boolean default true,
        )
    """
    try:
        from app.core.database import supabase

        if supabase is None:
            return None

        query = (
            supabase.table("vmd_agent_config")
            .select("*")
            .eq("agent_code", agent_code)
            .eq("is_active", True)
        )
        if tenant_id:
            query = query.eq("tenant_id", tenant_id)

        response = await query.limit(1).execute()
        rows = response.data or []

        if not rows:
            return None

        row = rows[0]
        return RoleConfig(
            agent_code=row["agent_code"],
            agent_name=row.get("agent_name", agent_code),
            system_prompt=row.get("system_prompt", ""),
            tool_whitelist=row.get("tool_whitelist", []),
            scene_codes=row.get("scene_codes", []),
            recommended_model_tier=row.get("recommended_model_tier", "medium"),
        )
    except Exception as e:
        # Table may not exist yet — that's fine, fall back to code defaults
        logger.debug(f"[RoleRegistry] DB lookup failed for {agent_code}: {e}")
        return None


# ─── Registry (eagerly loaded from code defaults) ───────────────────────────

ROLE_REGISTRY: dict[str, RoleConfig] = {}


def _init_registry():
    """Populate the registry from code-defined role modules."""
    for agent_code, module_path in _ROLE_MODULES.items():
        try:
            config = _load_role_from_module(module_path)
            ROLE_REGISTRY[agent_code] = config
        except Exception as e:
            logger.error(f"[RoleRegistry] Failed to load role {agent_code}: {e}")


# Initialize on import
_init_registry()


# ─── Public API ──────────────────────────────────────────────────────────────


async def get_role_config(agent_code: str, tenant_id: str | None = None) -> RoleConfig:
    """
    Get a role config by agent_code.

    Resolution order:
    1. DB (vmd_agent_config table) — allows per-tenant overrides
    2. Code defaults (role module files)
    3. Fallback to director_agent if unknown code

    Args:
        agent_code: The agent role code (e.g., "content_agent")
        tenant_id: Optional tenant ID for multi-tenant DB overrides

    Returns:
        RoleConfig instance
    """
    # 1. Try DB override
    db_config = await _load_role_from_db(agent_code, tenant_id)
    if db_config:
        logger.info(f"[RoleRegistry] Loaded {agent_code} from DB (tenant={tenant_id})")
        return db_config

    # 2. Code defaults
    if agent_code in ROLE_REGISTRY:
        return ROLE_REGISTRY[agent_code]

    # 3. Fallback
    logger.warning(f"[RoleRegistry] Unknown agent_code '{agent_code}', falling back to director_agent")
    return ROLE_REGISTRY.get("director_agent", RoleConfig(
        agent_code="director_agent",
        agent_name="市场总监Agent",
        system_prompt="你是一个市场营销助手。",
    ))


def get_all_roles() -> list[RoleConfig]:
    """Return all registered role configs (code defaults only; DB overrides require async)."""
    return list(ROLE_REGISTRY.values())


def get_role_config_sync(agent_code: str) -> RoleConfig:
    """
    Synchronous version of get_role_config — returns code defaults only (no DB).

    Useful for non-async contexts like graph construction.
    """
    if agent_code in ROLE_REGISTRY:
        return ROLE_REGISTRY[agent_code]
    return ROLE_REGISTRY.get("director_agent", RoleConfig(
        agent_code="director_agent",
        agent_name="市场总监Agent",
        system_prompt="你是一个市场营销助手。",
    ))
