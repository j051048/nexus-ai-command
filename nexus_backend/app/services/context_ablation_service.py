"""Context provider ablation utilities.

Runs a lightweight comparison between the full context ledger and hypothetical
provider removals. It is intentionally deterministic and safe for production
sampling; deeper model-based ablations can build on these outputs.
"""

from __future__ import annotations

from typing import Any


class ContextAblationService:
    def analyze_ledger(self, ledger: dict[str, Any]) -> dict[str, Any]:
        entries = [e for e in ledger.get("entries", []) if e.get("included")]
        total_tokens = max(sum(int(e.get("tokens_estimated") or 0) for e in entries), 1)
        ablations = []
        for entry in entries:
            tokens = int(entry.get("tokens_estimated") or 0)
            ablations.append(
                {
                    "provider": entry.get("provider"),
                    "removed_tokens": tokens,
                    "token_savings_ratio": round(tokens / total_tokens, 4),
                    "risk_hint": self._risk_hint(entry),
                    "truncated_reason": entry.get("truncated_reason"),
                }
            )
        ablations.sort(key=lambda x: x["removed_tokens"], reverse=True)
        return {
            "total_tokens": total_tokens,
            "provider_count": len(entries),
            "ablations": ablations,
        }

    def _risk_hint(self, entry: dict[str, Any]) -> str:
        provider = str(entry.get("provider") or "").lower()
        if "business" in provider or "rule" in provider or "知识" in provider:
            return "high_accuracy_risk"
        if "history" in provider or "memory" in provider or "记忆" in provider:
            return "medium_continuity_risk"
        return "low_to_medium_risk"


context_ablation_service = ContextAblationService()
