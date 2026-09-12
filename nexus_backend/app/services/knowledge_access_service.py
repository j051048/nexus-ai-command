"""Shared document authorization and lifecycle rules for retrieval and writing."""

from datetime import UTC, datetime
from typing import Any


def document_access_reason(
    document: dict[str, Any],
    *,
    user_id: str,
    organization_id: str | None = None,
    user_department: str | None = None,
) -> str | None:
    if not user_id:
        return "not_accessible"
    if (
        organization_id
        and str(document.get("organization_id") or "") != organization_id
    ):
        return "not_accessible"
    if document.get("deleted_at") or document.get("revoked_at"):
        return "not_current"
    visibility = document.get("visibility") or "organization"
    if visibility == "private" and str(document.get("owner_id") or "") != user_id:
        return "not_accessible"
    if visibility == "department" and (
        not user_department or document.get("department") != user_department
    ):
        return "not_accessible"
    if visibility not in {"private", "department", "organization", "public"}:
        return "not_accessible"
    if document.get("review_status") in {"rejected", "expired"}:
        return "not_current"
    expiry = document.get("valid_until")
    if expiry:
        try:
            deadline = datetime.fromisoformat(str(expiry).replace("Z", "+00:00"))
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=UTC)
            if deadline <= datetime.now(UTC):
                return "not_current"
        except ValueError:
            return "not_current"
    status = document.get("status")
    if status in {"failed", "error"}:
        return "ingestion_failed"
    if status not in {None, "ready", "completed"}:
        return "indexing"
    return None


async def document_department(
    db: Any, *, user_id: str, organization_id: str
) -> str | None:
    result = await (
        db.table("users")
        .select("department")
        .eq("id", user_id)
        .eq("organization_id", organization_id)
        .maybe_single()
        .execute()
    )
    return (result.data or {}).get("department")
