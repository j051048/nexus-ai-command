import pytest
from pydantic import ValidationError

from app.routers.tender_workspace import (
    WORKSPACE_SCHEMA_VERSION,
    TenderProjectCreate,
    TenderWorkspaceState,
    _project_code,
    _workspace_from_row,
)


def test_tender_workspace_defaults_are_versioned_and_human_reviewable():
    workspace = TenderWorkspaceState()

    assert workspace.schema_version == WORKSPACE_SCHEMA_VERSION
    assert workspace.active_stage == "intake"
    assert workspace.response_matrix == []
    assert workspace.review_gates == []


def test_legacy_project_rows_receive_a_safe_empty_workspace():
    row = _workspace_from_row({"id": 7, "metadata": {"legacy": True}})

    assert row["workspace"]["schema_version"] == WORKSPACE_SCHEMA_VERSION
    assert row["workspace"]["active_stage"] == "intake"
    assert row["metadata"]["legacy"] is True


def test_project_code_is_unique_and_operator_readable():
    first = _project_code()
    second = _project_code()

    assert first.startswith("BID-")
    assert first != second


def test_project_creation_rejects_invalid_money_and_short_names():
    with pytest.raises(ValidationError):
        TenderProjectCreate(name="A", estimated_value=-1)
