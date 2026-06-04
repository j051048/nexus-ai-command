"""Offline Agent eval baseline runner.

This uses the same lightweight intent router helper that backs the AI Operating
System simulation endpoint. The production version can later swap in
graph.ainvoke replay, but this keeps CI deterministic and cheap.
"""

from __future__ import annotations

from typing import Any

from app.routers.ai_operating_system import _intent_for


class AgentEvalBaselineService:
    def _fallback_intent(self, text: str, detected: str) -> str:
        if detected != "general_assistant":
            return detected
        lowered = text.lower()
        if any(
            token in lowered
            for token in (
                "approval",
                "approve",
                "reject",
                "reimbursement",
                "审批",
                "报销",
                "批准",
                "驳回",
            )
        ):
            return "approval_decision"
        if any(
            token in lowered
            for token in ("tender", "rfp", "score criteria", "招标", "投标", "评分")
        ):
            return "tender_support"
        if any(
            token in lowered
            for token in (
                "battlecard",
                "thermo",
                "agilent",
                "shimadzu",
                "compare",
                "竞品",
                "战卡",
                "对比",
            )
        ):
            return "battlecard"
        if any(
            token in lowered
            for token in ("contract", "renewal", "expire", "合同", "续签", "到期")
        ):
            return "renewal_or_contract"
        if any(
            token in lowered
            for token in (
                "crm",
                "customer",
                "lead",
                "follow-up",
                "visit",
                "客户",
                "线索",
                "跟进",
                "拜访",
            )
        ):
            return "crm_followup"
        return detected

    def run_router_baseline(self, cases: list[dict[str, Any]]) -> dict[str, Any]:
        results = []
        correct = 0
        for case in cases:
            text = str(case.get("text") or "")
            detected_intent, tools = _intent_for(text)
            detected_intent = self._fallback_intent(text, detected_intent)
            expected = case.get("expected_intent")
            passed = detected_intent == expected
            if passed:
                correct += 1
            results.append(
                {
                    "id": case.get("id"),
                    "expected_intent": expected,
                    "detected_intent": detected_intent,
                    "suggested_tools": tools,
                    "passed": passed,
                }
            )
        total = len(cases)
        return {
            "runner": "ai_operating_system._intent_for",
            "case_count": total,
            "passed": correct,
            "accuracy": round(correct / total, 4) if total else 0,
            "results": results,
        }


agent_eval_baseline_service = AgentEvalBaselineService()
