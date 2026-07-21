"""Human-feedback contract for artifact improvement candidates.

Feedback never mutates a production writing skill automatically.  It becomes
eligible for expert review only when the revised artifact remains grounded and
passes the same deterministic external-delivery gate.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any


def build_artifact_feedback_candidate(
    *,
    change_type: str,
    rating: int | None,
    original_content: str | None,
    revised_content: str | None,
    quality_before: dict[str, Any] | None,
    quality_after: dict[str, Any] | None,
    evidence_fingerprint: str | None,
) -> dict[str, Any]:
    """Return auditable metadata for the recommendation-only learning queue."""

    original = str(original_content or "")
    revised = str(revised_content or "")
    similarity = (
        SequenceMatcher(None, original, revised).ratio() if original or revised else 1.0
    )
    before_score = float((quality_before or {}).get("score") or 0)
    after_score = float((quality_after or {}).get("score") or 0)
    accepted_signal = change_type in {"accepted", "edited"} and (
        rating is None or rating >= 4
    )
    grounded = bool((quality_after or {}).get("ready"))
    promote_eligible = bool(
        accepted_signal
        and revised.strip()
        and evidence_fingerprint
        and grounded
        and after_score >= before_score
    )
    return {
        "schema_version": "artifact-feedback.v1",
        "learning_status": "review_candidate" if promote_eligible else "recorded",
        "promote_eligible": promote_eligible,
        "auto_apply": False,
        "content_similarity": round(similarity, 4),
        "quality_before": quality_before or {},
        "quality_after": quality_after or {},
        "evidence_fingerprint": evidence_fingerprint,
    }
