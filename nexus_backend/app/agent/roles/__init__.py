"""VMD Agent Role definitions. Each role has a system prompt, tool whitelist, and scene codes."""

from app.agent.roles.registry import ROLE_REGISTRY, get_all_roles, get_role_config

__all__ = ["get_role_config", "get_all_roles", "ROLE_REGISTRY"]
