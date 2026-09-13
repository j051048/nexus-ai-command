"""Verify that onboarding reflects usable, authorized data rather than UI clicks."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import BackgroundTasks, HTTPException


def query(data):
    result = MagicMock()
    for method in (
        "select",
        "eq",
        "order",
        "limit",
        "maybe_single",
        "insert",
        "update",
    ):
        getattr(result, method).return_value = result
    result.execute = AsyncMock(return_value=SimpleNamespace(data=data))
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,searchable", [("processing", False), ("ready", True), ("failed", False)]
)
async def test_readiness_distinguishes_upload_from_index_completion(
    monkeypatch, status, searchable
):
    from app.services import activation_readiness_service as service

    monkeypatch.setattr(service, "document_department", AsyncMock(return_value=None))
    doc = {"organization_id": "org-a", "owner_id": "u", "status": status}
    tables = {
        "documents": query(
            [doc, {**doc, "organization_id": "org-b", "status": "ready"}]
        ),
        "organization_activation_state": query({"facts_confirmed": True}),
        "artifacts": query([]),
    }
    db = MagicMock()
    db.table.side_effect = tables.__getitem__
    result = await service.activation_readiness(
        db, organization_id="org-a", user_id="u"
    )
    assert result["uploaded"] is True
    assert result["searchable"] is searchable
    assert result["facts_confirmed"] is searchable
    assert result["artifact_ready"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ready,authorized,expected",
    [(False, True, False), (True, False, False), (True, True, True)],
)
async def test_first_deliverable_requires_quality_and_current_source_access(
    monkeypatch, ready, authorized, expected
):
    from app.services import activation_readiness_service as service

    monkeypatch.setattr(service, "document_department", AsyncMock(return_value=None))
    access = AsyncMock(side_effect=None if authorized else HTTPException(403))
    monkeypatch.setattr(service, "require_current_evidence_access", access)
    tables = {
        "documents": query([]),
        "organization_activation_state": query({"facts_confirmed": True}),
        "artifacts": query([{"id": "a-1", "latest_version": 2}]),
        "artifact_versions": query({"quality_snapshot": {"ready": ready}}),
    }
    db = MagicMock()
    db.table.side_effect = tables.__getitem__
    result = await service.activation_readiness(
        db, organization_id="org-a", user_id="u"
    )
    assert result["artifact_ready"] is expected
    assert result["artifact_id"] == ("a-1" if expected else None)
    assert ("created_by", "u") in [
        call.args for call in tables["artifacts"].eq.call_args_list
    ]
    assert ("version_number", 2) in [
        call.args for call in tables["artifact_versions"].eq.call_args_list
    ]
    assert access.await_count == int(ready)


@pytest.mark.asyncio
async def test_bulk_import_enqueues_plaintext_instead_of_claiming_it_is_searchable(
    monkeypatch,
):
    from app.routers import documents

    monkeypatch.setattr(
        "app.services.knowledge_access_service.document_department",
        AsyncMock(return_value=None),
    )
    schedule = AsyncMock(return_value=True)
    monkeypatch.setattr(documents, "_schedule_ingestion", schedule)
    existing, inserted = query([]), query([{"id": "new-doc"}])
    db = MagicMock()
    document_queries = iter([existing, inserted])
    db.table.side_effect = lambda name: (
        query([]) if name == "knowledge_library" else next(document_queries)
    )
    req = SimpleNamespace(state=SimpleNamespace(db=db, org_id="org-a"))
    payload = documents.BulkImportRequest(
        documents=[
            documents.BulkImportDocumentItem(
                title="instrument.docx",
                content="technical reference content",
                visibility="private",
            )
        ]
    )
    response = await documents.bulk_import_documents(
        payload, req, BackgroundTasks(), user_id="u"
    )
    record = inserted.insert.call_args.args[0]
    assert record["status"] == "processing" and record["stage"] == "queued"
    assert record["name"] == "instrument.docx.txt"
    assert record["organization_id"] == "org-a" and record["owner_id"] == "u"
    assert record["visibility"] == "private"
    assert ("organization_id", "org-a") in [
        call.args for call in existing.eq.call_args_list
    ]
    assert schedule.await_args.kwargs["content"] == b"technical reference content"
    assert schedule.await_args.kwargs["organization_id"] == "org-a"
    assert response["data"]["results"][0]["ingestion_status"] == "queued"


@pytest.mark.asyncio
async def test_bulk_import_rejects_missing_tenant_before_db_access():
    from app.routers import documents

    db = MagicMock()
    req = SimpleNamespace(state=SimpleNamespace(db=db, org_id=None))
    payload = documents.BulkImportRequest(
        documents=[
            documents.BulkImportDocumentItem(title="a", content="reference content")
        ]
    )
    with pytest.raises(HTTPException):
        await documents.bulk_import_documents(
            payload, req, BackgroundTasks(), user_id="u"
        )
    db.table.assert_not_called()
