"""
MCP Permission Service - Auto-approve mechanism for MCP tools.

Reduces user confirmation prompts for trusted tools.
"""

import json
from pathlib import Path


class MCPPermissionService:
    """Manage MCP tool permissions and auto-approval"""

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path or ".kiro/settings/mcp.json"
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load MCP configuration"""
        config_file = Path(self.config_path)
        if not config_file.exists():
            return {"mcpServers": {}}

        try:
            with open(config_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"mcpServers": {}}

    def is_auto_approved(self, server_name: str, tool_name: str) -> bool:
        """Check if tool is in auto-approve list"""
        server_config = self.config.get("mcpServers", {}).get(server_name, {})
        auto_approve_list = server_config.get("autoApprove", [])
        return tool_name in auto_approve_list

    def get_auto_approve_tools(self, server_name: str) -> list[str]:
        """Get list of auto-approved tools for a server"""
        server_config = self.config.get("mcpServers", {}).get(server_name, {})
        return server_config.get("autoApprove", [])

    async def check_permission(
        self, server_name: str, tool_name: str, user_id: str
    ) -> dict[str, any]:
        """
        Check if tool execution requires user confirmation.

        Returns:
            {
                "approved": bool,
                "reason": "auto_approved" | "requires_confirmation"
            }
        """
        # Check auto-approve list
        if self.is_auto_approved(server_name, tool_name):
            return {"approved": True, "reason": "auto_approved"}

        # Requires user confirmation
        return {"approved": False, "reason": "requires_confirmation"}
