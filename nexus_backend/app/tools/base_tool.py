from abc import ABC, abstractmethod
from typing import Dict, Any

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
