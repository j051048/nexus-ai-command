from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.routers.document_inspection import inspectable_document, download_document_source


def database(row):
    query = MagicMock()
    for method in ("select", "eq", "maybe_single"):
        getattr(query, method).return_value = query
    query.execute = AsyncMock(return_value=SimpleNamespace(data=row))
    return SimpleNamespace(table=lambda _: query)


@pytest.mark.asyncio
async def test_private_document_hidden_even_if_db_returns_row():
    db = database({"organization_id": "org", "owner_id": "owner", "visibility": "private"})
    with pytest.raises(HTTPException):
        await inspectable_document(db, "doc", "org", "peer")


@pytest.mark.asyncio
async def test_expired_document_remains_inspectable_by_owner():
    doc = {"organization_id": "org", "owner_id": "owner", "visibility": "private", "review_status": "expired"}
    assert await inspectable_document(database(doc), "doc", "org", "owner") == doc


@pytest.mark.asyncio
async def test_source_download_rejects_cross_tenant_storage_pointer():
    doc = {"organization_id": "org", "owner_id": "owner", "visibility": "private", "source_storage_path": "other/knowledge/doc/private.pdf"}
    with pytest.raises(HTTPException):
        await download_document_source("doc", database(doc), "org", "owner")
