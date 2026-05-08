"""SOC2/ISO27001 evidence collection service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class ComplianceEvidenceService:
    """Writes compliance evidence into an append-only evidence table."""

    async def record_evidence(
        self,
        *,
        control_id: str,
        framework: str,
        evidence_type: str,
        description: str,
        actor_user_id: str | None = None,
        org_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from app.core.database import supabase

        payload = {
            "control_id": control_id,
            "framework": framework,
            "evidence_type": evidence_type,
            "description": description,
            "actor_user_id": actor_user_id,
            "org_id": org_id,
            "metadata": metadata or {},
            "created_at": datetime.now(UTC).isoformat(),
        }
        if supabase:
            await supabase.table("compliance_evidence_events").insert(payload).execute()
        return payload

    async def export_manifest(
        self,
        *,
        framework: str,
        start_at: str,
        end_at: str,
        org_id: str | None = None,
    ) -> list[dict[str, Any]]:
        from app.core.database import supabase

        if not supabase:
            return []

        query = (
            supabase.table("compliance_evidence_events")
            .select("*")
            .eq("framework", framework)
            .gte("created_at", start_at)
            .lt("created_at", end_at)
            .order("created_at", desc=False)
        )
        if org_id:
            query = query.eq("org_id", org_id)
        result = await query.execute()
        return result.data or []


compliance_evidence_service = ComplianceEvidenceService()
