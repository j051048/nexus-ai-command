"""
Third-party integration framework with abstract connector pattern.

Provides a registry-based architecture for integrating external services
(Slack, Teams, etc.) with standardized connect/disconnect/send lifecycle.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any

import httpx

logger = logging.getLogger(__name__)


class IntegrationType(Enum):
    """Categories of third-party integrations."""
    MESSAGING = "messaging"
    CRM = "crm"
    STORAGE = "storage"
    ANALYTICS = "analytics"
    TICKETING = "ticketing"


class IntegrationStatus(Enum):
    """Lifecycle status of an integration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    CONFIGURING = "configuring"


@dataclass
class IntegrationConfig:
    """Configuration for a specific integration instance."""
    integration_id: str
    org_id: str
    type: IntegrationType
    name: str
    credentials: Dict[str, str] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)
    status: IntegrationStatus = IntegrationStatus.INACTIVE

    def to_dict(self) -> Dict:
        return {
            "integration_id": self.integration_id,
            "org_id": self.org_id,
            "type": self.type.value,
            "name": self.name,
            "status": self.status.value,
            "settings": {k: v for k, v in self.settings.items()},
        }


class BaseConnector(ABC):
    """Abstract base connector for third-party services."""

    @abstractmethod
    async def connect(self, config: IntegrationConfig) -> bool:
        """Establish connection to the external service."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the external service."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the connection is healthy."""
        ...

    @abstractmethod
    async def send(self, action: str, payload: Dict) -> Dict:
        """Send a message/action to the external service."""
        ...


class SlackConnector(BaseConnector):
    """Slack integration connector."""

    def __init__(self):
        self._token: Optional[str] = None
        self._base_url = "https://slack.com/api"

    async def connect(self, config: IntegrationConfig) -> bool:
        self._token = config.credentials.get("bot_token")
        if not self._token:
            logger.error("Slack: bot_token not provided")
            return False
        return await self.health_check()

    async def disconnect(self) -> None:
        self._token = None

    async def health_check(self) -> bool:
        if not self._token:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{self._base_url}/auth.test",
                    headers={"Authorization": f"Bearer {self._token}"},
                )
                data = resp.json()
                return data.get("ok", False)
        except Exception as e:
            logger.warning(f"Slack health check failed: {e}")
            return False

    async def send(self, action: str, payload: Dict) -> Dict:
        if not self._token:
            return {"ok": False, "error": "not_connected"}

        endpoint_map = {
            "send_message": "chat.postMessage",
            "upload_file": "files.upload",
        }
        api_method = endpoint_map.get(action, action)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self._base_url}/{api_method}",
                    headers={"Authorization": f"Bearer {self._token}"},
                    json=payload,
                )
                return resp.json()
        except Exception as e:
            return {"ok": False, "error": str(e)}


class TeamsConnector(BaseConnector):
    """Microsoft Teams integration connector."""

    def __init__(self):
        self._webhook_url: Optional[str] = None

    async def connect(self, config: IntegrationConfig) -> bool:
        self._webhook_url = config.credentials.get("webhook_url")
        return bool(self._webhook_url)

    async def disconnect(self) -> None:
        self._webhook_url = None

    async def health_check(self) -> bool:
        return bool(self._webhook_url)

    async def send(self, action: str, payload: Dict) -> Dict:
        if not self._webhook_url:
            return {"ok": False, "error": "not_connected"}

        try:
            message = {
                "@type": "MessageCard",
                "summary": payload.get("text", "Notification"),
                "sections": [
                    {
                        "activityTitle": payload.get("title", "Nexus AI"),
                        "text": payload.get("text", ""),
                    }
                ],
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    self._webhook_url,
                    json=message,
                    headers={"Content-Type": "application/json"},
                )
                return {"ok": resp.status_code == 200, "status_code": resp.status_code}
        except Exception as e:
            return {"ok": False, "error": str(e)}


class ThirdPartyIntegrationService:
    """Registry and lifecycle manager for third-party integrations.

    NOTE: Only Slack and Teams connectors have real implementations.
    All other connector types are stubs (CRM, Storage, Analytics, Ticketing)
    and will return a development warning.
    """

    _DEV_WARNING = (
        "This connector is a stub implementation. "
        "Real integration is not yet available."
    )

    CONNECTOR_REGISTRY: Dict[str, type] = {
        "slack": SlackConnector,
        "teams": TeamsConnector,
    }

    def __init__(self):
        self._active_connections: Dict[str, BaseConnector] = {}
        self._configs: Dict[str, IntegrationConfig] = {}

    async def register(self, config: IntegrationConfig, db=None) -> bool:
        """Register a new integration configuration."""
        self._configs[config.integration_id] = config
        if db:
            try:
                await db.table("integrations").upsert(config.to_dict()).execute()
            except Exception as e:
                logger.warning(f"Failed to persist integration config: {e}")
        return True

    async def activate(self, integration_id: str) -> bool:
        """Activate an integration by connecting its connector."""
        config = self._configs.get(integration_id)
        if not config:
            return False

        connector_name = config.name.lower()
        connector_cls = self.CONNECTOR_REGISTRY.get(connector_name)
        if not connector_cls:
            logger.error(f"Unknown connector type: {connector_name}")
            return False

        connector = connector_cls()
        success = await connector.connect(config)
        if success:
            self._active_connections[integration_id] = connector
            config.status = IntegrationStatus.ACTIVE
            logger.info(f"Integration {integration_id} ({connector_name}) activated")
        else:
            config.status = IntegrationStatus.ERROR
        return success

    async def deactivate(self, integration_id: str) -> None:
        """Deactivate an integration."""
        connector = self._active_connections.pop(integration_id, None)
        if connector:
            await connector.disconnect()
        config = self._configs.get(integration_id)
        if config:
            config.status = IntegrationStatus.INACTIVE

    async def send(
        self, integration_id: str, action: str, payload: Dict
    ) -> Dict:
        """Send a message via an active integration."""
        connector = self._active_connections.get(integration_id)
        if not connector:
            return {"ok": False, "error": "integration_not_active"}
        return await connector.send(action, payload)

    def list_available_connectors(self) -> List[Dict]:
        """List all available connector types with implementation status."""
        result = []
        for name in self.CONNECTOR_REGISTRY:
            result.append({"name": name, "status": "available"})
        # Stubs for planned connectors
        for stub_name in ("salesforce", "hubspot", "jira", "notion", "google_drive"):
            result.append({
                "name": stub_name,
                "status": "planned",
                "_dev_warning": self._DEV_WARNING,
            })
        return result

    def list_integrations(self, org_id: str = None) -> List[Dict]:
        """List all registered integrations, optionally filtered by org."""
        results = []
        for config in self._configs.values():
            if org_id and config.org_id != org_id:
                continue
            results.append(config.to_dict())
        return results


# Global instance
third_party_integration_service = ThirdPartyIntegrationService()
