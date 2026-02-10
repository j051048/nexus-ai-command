from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class ConfirmationRequired(Exception):
    """Raised when a tool requires human confirmation before execution."""
    def __init__(self, preview_message: str, tool_name: str, args: Dict[str, Any]):
        self.preview_message = preview_message
        self.tool_name = tool_name
        self.args = args
        super().__init__(preview_message)


class BaseTool(ABC):
    """
    Abstract Base Class for all AI Agent Tools.
    Enforces the Strategy Pattern to decouple tool logic from the router.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass
        
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """JSON Schema for the tool parameters"""
        pass

    @property
    def required_role(self) -> str:
        """
        Optional: user role required to execute this tool.
        Returns 'all' by default, meaning no restriction.
        Possible values: 'boss', 'manager', 'sales', 'all', 'ai_assistant'
        """
        return "all"

    @property
    def is_irreversible(self) -> bool:
        """
        Whether this tool performs irreversible operations (approve, reject, delete, publish).
        If True, the system-level confirmation gate will intercept calls
        where confirm != True, regardless of what the LLM decides.
        """
        return False

    @property
    def confirmation_message(self) -> str:
        """
        Message to show when confirmation is required.
        Override in subclass for custom messages.
        """
        return "⚠️ 这是一个不可逆操作。请确认后再执行。"

    def check_confirmation(self, args: Dict[str, Any]) -> Optional[str]:
        """
        System-level confirmation gate.
        Called BEFORE run() for irreversible tools.
        Returns None if confirmed, or a preview message string if confirmation needed.
        
        This prevents the LLM from bypassing confirmation by auto-setting confirm=true.
        The system checks this BEFORE the tool's own logic runs.
        """
        if not self.is_irreversible:
            return None
        
        # System-level enforcement: if confirm is not explicitly True, block execution
        confirm = args.get("confirm", False)
        if confirm is True:
            return None  # Confirmed, allow execution
        
        return self.confirmation_message

    @abstractmethod
    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        """
        Execute the tool logic.
        :param args: Arguments parsed from the LLM's JSON output
        :param user_id: ID of the user invoking the tool
        :param config: AI Configuration (API Key, Base URL) for nested LLM calls
        :return: Text result to be fed back to the LLM
        """
        pass
