"""Promote production failure records into pending eval cases."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"\b1[3-9]\d{9}\b")
_ID_RE = re.compile(r"\b\d{15}(\d{2}[0-9Xx])?\b")


def redact_eval_text(text: str | None) -> str:
    if not text:
        return ""
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    text = _ID_RE.sub("[ID_NUMBER]", text)
    return text[:2000]


@dataclass
class PendingEvalCase:
    source_ref: str
    organization_id: str | None
    dimension: str
    input_json: dict[str, Any]
    expected_json: dict[str, Any]
    metadata_json: dict[str, Any]

    def to_row(self) -> dict[str, Any]:
        return {
            "source_type": "agent_failure_log",
            "source_ref": self.source_ref,
            "organization_id": self.organization_id,
            "status": "pending_label",
            "dimension": self.dimension,
            "input_json": self.input_json,
            "expected_json": self.expected_json,
            "metadata_json": self.metadata_json,
        }


class EvalCasePromotionService:
    def build_case_from_failure(self, row: dict[str, Any]) -> PendingEvalCase:
        source_ref = str(row.get("id") or row.get("source_ref") or "")
        if not source_ref:
            stable = "|".join(
                [
                    str(row.get("organization_id") or ""),
                    str(row.get("pattern_key") or ""),
                    str(row.get("user_message") or "")[:200],
                ]
            )
            source_ref = hashlib.sha256(stable.encode("utf-8")).hexdigest()[:24]

        user_message = redact_eval_text(row.get("user_message"))
        error_detail = redact_eval_text(row.get("error_detail"))
        error_type = row.get("error_type") or "unknown"

        dimension = {
            "hallucination": "hallucination",
            "prompt_injection": "safety",
            "permission_denied": "safety",
            "wrong_tool": "tool_selection",
            "wrong_params": "tool_selection",
            "timeout": "latency_cost",
            "negative_feedback": "task_completion",
        }.get(error_type, "task_completion")

        return PendingEvalCase(
            source_ref=source_ref,
            organization_id=row.get("organization_id") or row.get("org_id"),
            dimension=dimension,
            input_json={
                "query": user_message,
                "intent_summary": row.get("intent_summary"),
                "complexity": row.get("complexity"),
                "tool_calls": row.get("tool_calls") or [],
            },
            expected_json={
                "human_label_required": True,
                "failure_should_not_repeat": True,
            },
            metadata_json={
                "error_type": error_type,
                "severity": row.get("severity") or "medium",
                "pattern_key": row.get("pattern_key"),
                "error_detail": error_detail,
            },
        )

    async def promote_recent_failures(
        self,
        *,
        db,
        org_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = db.table("agent_failure_logs").select("*").order(
            "created_at", desc=True
        ).limit(limit)
        if org_id:
            query = query.eq("organization_id", org_id)
        result = await query.execute()

        cases = [self.build_case_from_failure(row) for row in result.data or []]
        rows = [case.to_row() for case in cases]
        if not rows:
            return []

        inserted = await db.table("agent_eval_cases").upsert(
            rows,
            on_conflict="source_type,source_ref",
        ).execute()
        return inserted.data or rows


eval_case_promotion_service = EvalCasePromotionService()
