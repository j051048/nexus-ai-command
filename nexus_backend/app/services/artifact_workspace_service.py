"""Permission-aware result reads and revision provenance."""

from uuid import UUID

from app.core.errors import ErrorCode, api_error
from app.services.knowledge_access_service import (
    document_access_reason,
    document_department,
)


async def load_artifact_snapshot(db, organization_id, artifact_id):
    result = (
        await db.table("artifacts")
        .select("*")
        .eq("organization_id", organization_id)
        .eq("id", str(artifact_id))
        .maybe_single()
        .execute()
    )
    artifact = result.data
    if not artifact:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "成果不存在或无权访问")
    result = (
        await db.table("artifact_versions")
        .select("*")
        .eq("organization_id", organization_id)
        .eq("artifact_id", str(artifact_id))
        .eq("version_number", artifact.get("latest_version") or 1)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "成果版本不存在")
    return artifact, result.data


async def require_current_evidence_access(db, organization_id, user_id, version):
    records = (version.get("evidence_snapshot") or {}).get("records") or []
    ids = list(dict.fromkeys(str(row.get("document_id") or "") for row in records))
    if not ids:
        return

    def denied():
        return api_error(
            ErrorCode.RESOURCE_CONFLICT, "引用资料已变更或无权访问，请重新选择资料生成"
        )

    try:
        for document_id in ids:
            UUID(document_id)
    except ValueError:
        raise denied() from None
    result = (
        await db.table("documents")
        .select(
            "id,organization_id,owner_id,visibility,department,status,review_status,valid_until,source_version"
        )
        .eq("organization_id", organization_id)
        .in_("id", ids)
        .execute()
    )
    documents = {str(row["id"]): row for row in result.data or []}
    department = None
    if any(row.get("visibility") == "department" for row in documents.values()):
        department = await document_department(
            db, user_id=user_id, organization_id=organization_id
        )
    for record in records:
        document = documents.get(str(record.get("document_id")))
        if (
            not document
            or document_access_reason(
                document,
                user_id=user_id,
                organization_id=organization_id,
                user_department=department,
            )
            is not None
        ):
            raise denied()
        if record.get("source_version") != document.get("source_version"):
            raise denied()


def result_preview(artifact, version):
    metadata = artifact.get("metadata") or {}
    generation = metadata.get("generation") or {}
    evidence = version.get("evidence_snapshot") or {}
    return {
        "content_markdown": version.get("content_markdown") or "",
        "requirements": metadata.get("content_contract") or {},
        "sources": [
            {
                "title": row.get("title"),
                "source_version": row.get("source_version"),
                "document_id": row.get("document_id"),
            }
            for row in evidence.get("records") or []
        ],
        "usage": generation.get("usage") or {},
        "usage_scope": generation.get("usage_scope") or "unknown",
        "checkpoint_hits": generation.get("checkpoint_hits") or 0,
        "revision_of": metadata.get("revision_of"),
    }


def revision_payload(artifact, version, instructions, request_key):
    metadata = artifact.get("metadata") or {}
    contract = metadata.get("content_contract") or {}
    return {
        "original_request": f"{str(artifact.get('source_request') or '')[:3500]}\n本次修订要求：{instructions}",
        "source_content": "",
        "title": artifact["title"],
        "artifact_type": artifact["artifact_type"],
        "audience": artifact.get("audience") or "customer",
        "requested_formats": metadata.get("requested_formats") or ["docx", "pdf"],
        "customer_context": metadata.get("customer_context") or {},
        "selected_document_ids": list(
            dict.fromkeys(
                row["document_id"]
                for row in (version.get("evidence_snapshot") or {}).get("records", [])
            )
        )[:20],
        "delivery_requirements": contract.get("delivery_requirements") or {},
        "target_character_count": contract.get("target_character_count"),
        "revision_of": str(artifact["id"]),
        "review_confirmed": False,
        "request_key": request_key,
    }
