import pytest

from app.services.knowledge_access_service import document_access_reason


@pytest.mark.parametrize("patch,reason", [
    ({}, None),
    ({"organization_id": "org-b"}, "not_accessible"),
    ({"visibility": "private", "owner_id": "other"}, "not_accessible"),
    ({"visibility": "private", "owner_id": "user"}, None),
    ({"visibility": "department", "department": "qa"}, "not_accessible"),
    ({"valid_until": "2020-01-01"}, "not_current"),
    ({"valid_until": "invalid"}, "not_current"),
    ({"review_status": "rejected"}, "not_current"),
    ({"status": "processing"}, "indexing"),
    ({"status": "failed"}, "ingestion_failed"),
])
def test_document_read_policy(patch, reason):
    document = {"organization_id": "org-a", "status": "ready", **patch}
    assert document_access_reason(document, user_id="user", organization_id="org-a") == reason


def test_department_and_anonymous_access():
    doc = {"visibility": "department", "department": "qa"}
    assert document_access_reason(doc, user_id="user", user_department="qa") is None
    assert document_access_reason(doc, user_id="", user_department="qa") == "not_accessible"
