"""Human inspection uses document ACLs independently of retrieval readiness."""

import json
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.core.auth import get_current_org_id, get_current_user_id
from app.core.dependencies import get_request_db
from app.core.errors import ErrorCode, api_error, api_success
from app.services.knowledge_access_service import (
    document_access_reason,
    document_department,
)
from app.services.knowledge_ingestion_service import _storage_request

router = APIRouter()


async def inspectable_document(db, document_id, organization_id, user_id):
    result = (
        await db.table("documents")
        .select("*")
        .eq("id", str(document_id))
        .eq("organization_id", organization_id)
        .maybe_single()
        .execute()
    )
    document = result.data
    if not document:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "资料不存在或无权访问")
    department = (
        await document_department(db, user_id=user_id, organization_id=organization_id)
        if document.get("visibility") == "department"
        else None
    )
    # Allow inspection of expired/failed documents, but never bypass visibility.
    access_document = {**document, "deleted_at": None, "revoked_at": None}
    if (
        document_access_reason(
            access_document,
            user_id=user_id,
            organization_id=organization_id,
            user_department=department,
        )
        == "not_accessible"
    ):
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "资料不存在或无权访问")
    if document.get("deleted_at") or document.get("revoked_at"):
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "资料已撤回")
    return document


@router.get("/{document_id}/preview")
async def preview_document(
    document_id: UUID,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    document = await inspectable_document(db, document_id, organization_id, user_id)
    extracted = document.get("extracted_data") or {}
    if isinstance(extracted, str):
        try:
            extracted = json.loads(extracted)
        except ValueError:
            extracted = {}
    if not isinstance(extracted, dict):
        extracted = {}
    result = (
        await db.table("document_embeddings")
        .select("id,chunk_index,content")
        .eq("document_id", str(document_id))
        .eq("organization_id", organization_id)
        .order("chunk_index")
        .limit(21)
        .execute()
    )
    chunks = result.data or []
    text = str(extracted.get("full_text_context") or "")
    if not text:
        text = "\n\n".join(str(row.get("content") or "") for row in chunks[:20])
    facts = {
        key: value
        for key, value in extracted.items()
        if key not in {"full_text_context", "summary", "tags"}
    }
    return api_success(
        data={
            "id": str(document_id),
            "name": document.get("name"),
            "status": document.get("status"),
            "review_status": document.get("review_status"),
            "source_version": document.get("source_version"),
            "valid_until": document.get("valid_until"),
            "quality_score": document.get("quality_score"),
            "summary": extracted.get("summary") or "",
            "content": text[:40000],
            "truncated": len(text) > 40000
            or (len(chunks) > 20 and not extracted.get("full_text_context")),
            "facts": {
                key: (
                    json.dumps(value, ensure_ascii=False)[:2000]
                    if not isinstance(value, str)
                    else value[:2000]
                )
                for key, value in list(facts.items())[:20]
            },
            "citations": [
                {
                    "id": row["id"],
                    "index": row.get("chunk_index"),
                    "excerpt": str(row.get("content") or "")[:600],
                }
                for row in chunks[:20]
            ],
            "has_original": bool(document.get("source_storage_path")),
        }
    )


@router.get("/{document_id}/source")
async def download_document_source(
    document_id: UUID,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    document = await inspectable_document(db, document_id, organization_id, user_id)
    path = str(document.get("source_storage_path") or "")
    if not path.startswith(
        f"{organization_id}/knowledge/{document_id}/"
    ) or ".." in path.split("/"):
        raise api_error(
            ErrorCode.RESOURCE_NOT_FOUND, "原文件尚未保存，请联系资料管理员"
        )
    content = await _storage_request("GET", path)
    name = str(document.get("name") or "document").replace("\\", "/").rsplit("/", 1)[-1]
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name, safe='')}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
