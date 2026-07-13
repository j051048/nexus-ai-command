"""Context provider ablation utilities.

Runs a lightweight comparison between the full context ledger and hypothetical
provider removals. It is intentionally deterministic and safe for production
sampling; deeper model-based ablations can build on these outputs.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

ContextEvaluator = Callable[[set[str]], Awaitable[dict[str, Any]]]


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

    async def evaluate_counterfactuals(
        self,
        ledger: dict[str, Any],
        evaluator: ContextEvaluator,
        *,
        max_providers: int = 8,
    ) -> dict[str, Any]:
        """Actually rerun quality evaluation with each provider removed.

        The evaluator receives the provider exclusion set and returns at least
        ``quality_score`` and optionally ``tokens``/``cost_usd``. Keeping the
        execution callback outside this service makes offline deterministic
        evaluators and sampled model-based evaluations use the same contract.
        """
        static = self.analyze_ledger(ledger)
        baseline = await evaluator(set())
        baseline_quality = float(baseline.get("quality_score") or 0.0)
        results: list[dict[str, Any]] = []
        for item in static["ablations"][:max_providers]:
            provider = str(item.get("provider") or "")
            candidate = await evaluator({provider})
            candidate_quality = float(candidate.get("quality_score") or 0.0)
            results.append(
                {
                    **item,
                    "quality_score": candidate_quality,
                    "quality_delta": round(candidate_quality - baseline_quality, 4),
                    "tokens": int(candidate.get("tokens") or 0),
                    "cost_usd": float(candidate.get("cost_usd") or 0.0),
                    "removal_safe": candidate_quality >= baseline_quality - 0.02,
                }
            )
        return {
            "baseline": baseline,
            "evaluated_provider_count": len(results),
            "counterfactuals": results,
        }

    def _risk_hint(self, entry: dict[str, Any]) -> str:
        provider = str(entry.get("provider") or "").lower()
        if "business" in provider or "rule" in provider or "知识" in provider:
            return "high_accuracy_risk"
        if "history" in provider or "memory" in provider or "记忆" in provider:
            return "medium_continuity_risk"
        return "low_to_medium_risk"


context_ablation_service = ContextAblationService()
