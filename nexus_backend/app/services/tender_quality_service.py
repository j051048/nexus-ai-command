"""Deterministic Bid/No-Bid, ownership and delivery checks for tender workspaces."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def evaluate_tender_workspace(
    project: dict[str, Any], workspace: dict[str, Any]
) -> dict[str, Any]:
    matrix = [
        item
        for item in workspace.get("response_matrix") or []
        if isinstance(item, dict)
    ]
    gates = [
        item for item in workspace.get("review_gates") or [] if isinstance(item, dict)
    ]
    sections = [
        item for item in workspace.get("draft_sections") or [] if isinstance(item, dict)
    ]
    mandatory = [item for item in matrix if item.get("category") == "mandatory"]
    blocked = [item for item in mandatory if item.get("status") == "blocked"]
    owner_gaps = [item for item in matrix if not str(item.get("owner") or "").strip()]
    evidence_gaps = [
        item
        for item in matrix
        if not str(item.get("evidence_ref") or "").strip()
        and item.get("category") in {"mandatory", "technical", "scoring"}
    ]
    response_gaps = [
        item for item in matrix if not str(item.get("response") or "").strip()
    ]
    required_gates = [item for item in gates if item.get("required", True)]
    pending_gates = [item for item in required_gates if item.get("status") != "passed"]
    approved_sections = [item for item in sections if item.get("status") == "approved"]

    deadline_days = None
    deadline = project.get("bid_deadline") or project.get("deadline")
    if deadline:
        try:
            parsed = datetime.fromisoformat(str(deadline).replace("Z", "+00:00"))
            deadline_days = (parsed.astimezone(UTC) - datetime.now(UTC)).days
        except ValueError:
            deadline_days = None

    response_score = (
        (len(matrix) - len(response_gaps)) / len(matrix) * 25 if matrix else 0
    )
    evidence_score = (
        (len(matrix) - len(evidence_gaps)) / len(matrix) * 25 if matrix else 0
    )
    owner_score = (len(matrix) - len(owner_gaps)) / len(matrix) * 15 if matrix else 0
    gate_score = (
        (len(required_gates) - len(pending_gates)) / len(required_gates) * 20
        if required_gates
        else 0
    )
    section_score = len(approved_sections) / len(sections) * 15 if sections else 0
    score = round(
        response_score + evidence_score + owner_score + gate_score + section_score, 1
    )
    no_go_reasons = []
    if blocked:
        no_go_reasons.append(f"{len(blocked)} 个否决项仍处于阻塞状态")
    if deadline_days is not None and deadline_days < 0:
        no_go_reasons.append("投标截止时间已过")
    if not matrix:
        no_go_reasons.append("尚未形成逐条应答矩阵")
    review_reasons = []
    if evidence_gaps:
        review_reasons.append(f"{len(evidence_gaps)} 项关键响应缺少证据")
    if owner_gaps:
        review_reasons.append(f"{len(owner_gaps)} 项尚未指定责任人")
    if pending_gates:
        review_reasons.append(f"{len(pending_gates)} 个必检门禁未通过")
    can_deliver = score >= 85 and not no_go_reasons and not review_reasons
    decision = "bid" if can_deliver else "no_bid" if no_go_reasons else "review"
    return {
        "schema_version": "tender-quality.v1",
        "score": score,
        "decision": decision,
        "can_deliver": can_deliver,
        "deadline_days": deadline_days,
        "no_go_reasons": no_go_reasons,
        "review_reasons": review_reasons,
        "counts": {
            "requirements": len(matrix),
            "blocked_mandatory": len(blocked),
            "response_gaps": len(response_gaps),
            "evidence_gaps": len(evidence_gaps),
            "owner_gaps": len(owner_gaps),
            "pending_gates": len(pending_gates),
            "approved_sections": len(approved_sections),
        },
        "delivery_checklist": [
            {
                "key": "matrix",
                "label": "逐条应答矩阵",
                "ready": bool(matrix) and not response_gaps,
            },
            {"key": "evidence", "label": "参数与资质证据", "ready": not evidence_gaps},
            {"key": "owners", "label": "责任人与截止时间", "ready": not owner_gaps},
            {
                "key": "gates",
                "label": "商务、技术与签章复核",
                "ready": not pending_gates,
            },
            {
                "key": "sections",
                "label": "批准后的标书章节",
                "ready": bool(sections) and len(approved_sections) == len(sections),
            },
        ],
    }
