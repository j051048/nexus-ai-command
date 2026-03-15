"""
Service Layer Interface Protocols

Defines structural typing protocols for core services, enabling:
- Dependency inversion (routers depend on abstractions, not implementations)
- Easy mocking in tests (no inheritance required)
- Gradual adoption (existing classes auto-satisfy protocols if signatures match)

Usage:
    from app.services.interfaces import CRMServiceProtocol

    def get_crm() -> CRMServiceProtocol:
        from app.services.crm_service import crm_service
        return crm_service
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# 1. CRM Service Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class CRMServiceProtocol(Protocol):
    """
    Protocol for CRM / sales lead management operations.

    Implementations: crm_service.py, clue_service.py
    """

    async def get_leads(
        self,
        tenant_id: str,
        *,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """Retrieve a paginated list of leads for the given tenant."""
        ...

    async def create_lead(
        self,
        tenant_id: str,
        data: dict[str, Any],
        *,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new lead and return the created record."""
        ...

    async def update_lead(
        self,
        tenant_id: str,
        lead_id: str,
        data: dict[str, Any],
        *,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing lead and return the updated record."""
        ...


# ---------------------------------------------------------------------------
# 2. Approval Service Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class ApprovalServiceProtocol(Protocol):
    """
    Protocol for multi-level approval workflow operations.

    Implementations: approval_chain.py, approval_service.py
    """

    async def submit(
        self,
        tenant_id: str,
        approval_type: str,
        data: dict[str, Any],
        *,
        requester_id: str,
    ) -> dict[str, Any]:
        """Submit a new approval request and return the created record."""
        ...

    async def approve(
        self,
        tenant_id: str,
        request_id: str,
        *,
        approver_id: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Approve a pending request and return the updated record."""
        ...

    async def reject(
        self,
        tenant_id: str,
        request_id: str,
        *,
        approver_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Reject a pending request with a reason."""
        ...

    async def list_pending(
        self,
        tenant_id: str,
        *,
        approver_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """List pending approval requests, optionally filtered by approver."""
        ...


# ---------------------------------------------------------------------------
# 3. Storage Service Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class StorageServiceProtocol(Protocol):
    """
    Protocol for file storage operations (upload, download, delete).

    Implementations: Supabase Storage wrapper, S3 adapter, etc.
    """

    async def upload(
        self,
        tenant_id: str,
        bucket: str,
        path: str,
        content: bytes,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Upload a file and return metadata including the storage path
        and a public/signed URL.
        """
        ...

    async def download(
        self,
        tenant_id: str,
        bucket: str,
        path: str,
    ) -> bytes:
        """Download a file and return its raw bytes."""
        ...

    async def delete(
        self,
        tenant_id: str,
        bucket: str,
        path: str,
    ) -> bool:
        """Delete a file. Returns True if successful."""
        ...


# ---------------------------------------------------------------------------
# 4. Event Bus Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class EventBusProtocol(Protocol):
    """
    Protocol for publishing domain events.

    Implementations: event_bus.py (in-process), future Redis Pub/Sub adapter
    """

    async def emit(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        """Publish a domain event."""
        ...


# ---------------------------------------------------------------------------
# 5. LLM Gateway Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMGatewayProtocol(Protocol):
    """
    Protocol for LLM model gateway operations.

    Implementations: llm_gateway/ package
    """

    async def chat(
        self,
        scene_code: str,
        agent_code: str,
        user_id: str,
        org_id: str,
        system_prompt: str,
        messages: list[dict],
        *,
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        request_id: str | None = None,
    ) -> Any:
        """Execute a chat completion through the gateway."""
        ...

    async def embedding(
        self,
        texts: list[str],
        org_id: str,
        *,
        model_code: str | None = None,
    ) -> Any:
        """Generate embeddings for a list of texts."""
        ...

    def invalidate_cache(self, org_id: str | None = None) -> None:
        """Clear model config and schedule rule caches."""
        ...
