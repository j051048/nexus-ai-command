"""Read-only first-value progress derived from authorized business records."""

from fastapi import HTTPException

from app.services.artifact_workspace_service import require_current_evidence_access
from app.services.knowledge_access_service import (
    document_access_reason,
    document_department,
)


async def activation_readiness(db, *, organization_id: str, user_id: str) -> dict:
    result = await (
        db.table("documents")
        .select(
            "id,organization_id,owner_id,visibility,department,status,review_status,valid_until"
        )
        .eq("organization_id", organization_id)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    department = await document_department(
        db, user_id=user_id, organization_id=organization_id
    )
    reasons = [
        document_access_reason(
            row,
            user_id=user_id,
            organization_id=organization_id,
            user_department=department,
        )
        for row in result.data or []
    ]
    uploaded = sum(
        reason in {None, "indexing", "ingestion_failed"} for reason in reasons
    )
    ready = sum(reason is None for reason in reasons)
    activation = await (
        db.table("organization_activation_state")
        .select("facts_confirmed")
        .eq("organization_id", organization_id)
        .maybe_single()
        .execute()
    )
    artifacts = await (
        db.table("artifacts")
        .select("id,latest_version")
        .eq("organization_id", organization_id)
        .eq("created_by", user_id)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    artifact_id = None
    for artifact in artifacts.data or []:
        version = await (
            db.table("artifact_versions")
            .select("quality_snapshot,evidence_snapshot")
            .eq("organization_id", organization_id)
            .eq("artifact_id", artifact["id"])
            .eq("version_number", artifact.get("latest_version") or 1)
            .maybe_single()
            .execute()
        )
        if not version.data or not (version.data.get("quality_snapshot") or {}).get(
            "ready"
        ):
            continue
        try:
            await require_current_evidence_access(
                db, organization_id, user_id, version.data
            )
        except HTTPException:
            continue
        artifact_id = artifact["id"]
        break
    return {
        "organization_id": organization_id,
        "user_id": user_id,
        "uploaded": uploaded > 0,
        "searchable": ready > 0,
        "facts_confirmed": ready > 0
        and bool((activation.data or {}).get("facts_confirmed")),
        "artifact_ready": artifact_id is not None,
        "artifact_id": artifact_id,
        "scope": "latest_100_documents_and_20_personal_artifacts",
    }
