"""Source contracts for the critical delivery path.

These tests exist because the quality platform was once fully implemented but
not wired into generation. They fail the moment an integration point is dropped
by a refactor, which is cheaper than discovering it in a customer deliverable.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def test_generation_service_uses_unified_quality_gate_and_templates():
    service = read("nexus_backend/app/services/artifact_generation_service.py")

    assert "from app.services.artifact_llm_judge import evaluate_delivery_package" in service
    assert "evaluate_delivery_package(" in service
    assert "get_optimal_template(" in service
    assert "build_template_system_prompt(" in service


def test_quality_platform_routes_are_registered_and_authenticated():
    router_source = read("nexus_backend/app/routers/artifact_quality_platform.py")
    route_groups = read("nexus_backend/app/startup/route_groups.py")

    assert "artifact_quality_platform.router" in route_groups

    decorator_positions = [
        match.start()
        for match in re.finditer(r"@router\.(get|post|put|patch|delete)\(", router_source)
    ]
    assert decorator_positions, "artifact quality router must expose endpoints"

    for position in decorator_positions:
        handler = router_source[position : position + 900]
        assert "Depends(" in handler, (
            "every artifact quality endpoint must declare an authentication "
            "dependency; see app/core/api_auth_matrix.py for the public allowlist"
        )


def test_delivery_scan_covers_pii_and_internal_markers():
    scanner = read("nexus_backend/app/services/artifact_delivery_scan.py")

    for token in ("phone", "id_card", "email", "internal", "承诺"):
        assert token in scanner, f"delivery scan must keep the {token} rule"


def test_document_quality_slo_targets_are_pinned():
    slo = read("nexus_backend/app/services/artifact_quality_slo.py")

    assert '"target": 0.90' in slo
    assert '"target": 85.0' in slo
    assert '"target": 90.0' in slo


def test_learning_candidates_require_human_approval_before_template_promotion():
    feedback = read("nexus_backend/app/services/artifact_feedback_loop.py")
    router_source = read("nexus_backend/app/routers/artifact_quality_platform.py")
    migrations = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted((ROOT / "supabase" / "migrations").glob("*.sql"))
    )

    assert "learning_status" in feedback
    # The pipeline may only ever open a candidate ...
    assert 'LEARNING_OPEN_STATUSES = ("recorded", "review_candidate")' in feedback
    # ... and approving/rejecting is a human-only transition.
    assert 'LEARNING_TERMINAL_STATUSES = ("approved", "rejected")' in feedback
    assert '"auto_apply": False' in feedback, (
        "approval must stay auditable and never auto-write a production template"
    )
    assert '@router.post("/learning-candidates/{event_id}/review")' in router_source
    assert "review_learning_candidate(" in router_source
    assert "require_admin" in router_source, (
        "only an org admin may approve a learning candidate"
    )
    assert "reviewed_by" in migrations and "reviewed_at" in migrations, (
        "the review decision must be persisted with reviewer identity and time"
    )
