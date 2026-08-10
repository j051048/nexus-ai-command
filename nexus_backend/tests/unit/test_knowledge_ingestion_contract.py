import pytest

from app.services import knowledge_ingestion_service
from app.services.knowledge_ingestion_service import (
    build_source_storage_path,
    persist_source_file,
)


def test_source_storage_path_is_tenant_scoped_and_sanitized():
    path = build_source_storage_path(
        organization_id="org-1",
        document_id="doc-1",
        filename="../产品 资料?.docx",
    )
    assert path.startswith("org-1/knowledge/doc-1/")
    assert ".." not in path
    assert " " not in path
    assert "?" not in path


class _FakeDb:
    def table(self, _name):
        return self

    def update(self, _payload):
        return self

    def eq(self, *_args):
        return self

    async def execute(self):
        return object()


@pytest.mark.asyncio
async def test_source_persistence_uses_supabase_upload_semantics(monkeypatch):
    requests = []

    async def fake_storage_request(method, path, **kwargs):
        requests.append((method, path, kwargs))
        return b""

    monkeypatch.setattr(
        knowledge_ingestion_service,
        "_storage_request",
        fake_storage_request,
    )
    path = await persist_source_file(
        _FakeDb(),
        organization_id="org-1",
        document_id="doc-1",
        filename="产品资料.docx",
        content=b"docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert path
    assert requests[0][0] == "POST"
    assert requests[0][2]["content"] == b"docx"
