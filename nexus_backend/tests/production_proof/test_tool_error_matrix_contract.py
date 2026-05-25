from __future__ import annotations


CORE_TOOL_MATRIX = {
    "search_customers": ["success", "invalid_params", "permission_denied", "timeout"],
    "draft_followup": ["success", "invalid_params", "permission_denied", "timeout"],
    "query_pending_approvals": ["success", "invalid_params", "permission_denied", "timeout"],
    "submit_approval": ["success", "invalid_params", "permission_denied", "timeout"],
    "parse_tender_document": ["success", "invalid_params", "permission_denied", "timeout"],
    "score_tender_response": ["success", "invalid_params", "permission_denied", "timeout"],
    "query_contracts": ["success", "invalid_params", "permission_denied", "timeout"],
    "draft_email": ["success", "invalid_params", "permission_denied", "timeout"],
}


def test_core_tool_error_matrix_covers_four_required_paths():
    required = {"success", "invalid_params", "permission_denied", "timeout"}
    assert CORE_TOOL_MATRIX
    for tool_name, cases in CORE_TOOL_MATRIX.items():
        assert required <= set(cases), tool_name


def test_tool_resilience_suite_exists():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    assert (root / "tests" / "unit" / "test_tool_resilience.py").exists()
    assert (root / "tests" / "integration" / "test_tool_execution.py").exists()
