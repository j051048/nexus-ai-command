"""
RAG Evaluation Service

Provides quantitative evaluation of retrieval quality using:
1. RAGAS metrics (faithfulness, relevancy, precision, recall) when available
2. Simple keyword-based fallback metrics otherwise

Usage:
    from app.services.rag_evaluator import rag_evaluator
    result = await rag_evaluator.evaluate_retrieval(test_cases, org_id="...")
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class RAGEvaluator:
    """Evaluate RAG pipeline quality with standard metrics."""

    async def evaluate_retrieval(
        self,
        test_cases: list[dict],
        org_id: str,
        user_id: str = "eval_user",
    ) -> dict[str, Any]:
        """
        Run retrieval evaluation on a set of test cases.

        Each test_case: {
            "query": str,
            "expected_keywords": list[str] (optional),
            "ground_truth": str (optional),
        }

        Returns aggregated metrics dict.
        """
        from app.services.vector_service import vector_service

        results = []
        for case in test_cases:
            query = case["query"]
            try:
                search_result = await vector_service.search(
                    query, user_id, org_id=org_id, require_org_id=False
                )
            except Exception as e:
                logger.warning(f"Search failed for eval query '{query}': {e}")
                search_result = ""

            results.append(
                {
                    "query": query,
                    "retrieved_context": search_result,
                    "retrieved_items": self._normalize_retrieval(search_result),
                    "expected_keywords": case.get("expected_keywords", []),
                    "expected_doc_ids": case.get("expected_doc_ids", []),
                    "ground_truth": case.get("ground_truth", ""),
                    "category": case.get("category", ""),
                }
            )

        # Try RAGAS first, fall back to simple metrics
        metrics = self._compute_ragas_metrics(results)
        if metrics["status"] == "fallback":
            simple = self._compute_simple_metrics(results)
            metrics["metrics"].update(simple["metrics"])
        metrics["metrics"].update(self._compute_retrieval_metrics(results)["metrics"])

        return metrics

    def _normalize_retrieval(self, value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [v if isinstance(v, dict) else {"text": str(v)} for v in value]
        if isinstance(value, dict):
            items = value.get("items") or value.get("results") or []
            if isinstance(items, list):
                return [v if isinstance(v, dict) else {"text": str(v)} for v in items]
            return [value]
        text = str(value or "")
        chunks = [c.strip() for c in text.split("\n\n") if c.strip()]
        return [{"text": c} for c in chunks[:10]]

    def _compute_ragas_metrics(self, results: list[dict]) -> dict[str, Any]:
        """Compute RAGAS metrics from evaluation results."""
        try:
            from datasets import Dataset
            from ragas import evaluate
            from ragas.metrics import (
                answer_relevancy,
                context_precision,
                faithfulness,
            )

            # Filter results with ground_truth for supervised metrics
            supervised = [r for r in results if r.get("ground_truth")]

            if not supervised:
                logger.info(
                    "No ground_truth provided, skipping RAGAS supervised metrics"
                )
                return {
                    "metrics": {},
                    "sample_count": len(results),
                    "status": "fallback",
                }

            data = {
                "question": [r["query"] for r in supervised],
                "contexts": [[r["retrieved_context"]] for r in supervised],
                "ground_truth": [r["ground_truth"] for r in supervised],
                "answer": [r["retrieved_context"] for r in supervised],
            }
            dataset = Dataset.from_dict(data)

            score = evaluate(
                dataset,
                metrics=[context_precision, answer_relevancy, faithfulness],
            )
            return {
                "metrics": {
                    k: round(v, 4)
                    for k, v in dict(score).items()
                    if isinstance(v, int | float)
                },
                "sample_count": len(supervised),
                "status": "ragas",
            }
        except ImportError:
            logger.info("RAGAS not installed, using simple metrics")
            return {"metrics": {}, "sample_count": len(results), "status": "fallback"}
        except Exception as e:
            logger.error(f"RAGAS evaluation failed: {e}")
            return {"metrics": {}, "sample_count": len(results), "status": "fallback"}

    def _compute_simple_metrics(self, results: list[dict]) -> dict[str, Any]:
        """
        Simple keyword-based metrics that work without external dependencies.
        Always available as a baseline.
        """
        total = len(results)
        if total == 0:
            return {
                "metrics": {"retrieval_rate": 0, "keyword_hit_rate": 0},
                "sample_count": 0,
                "status": "fallback",
            }

        # Retrieval rate: how many queries returned actual results (not "未找到")
        retrieved = sum(1 for r in results if "未找到" not in r["retrieved_context"])
        retrieval_rate = retrieved / total

        # Keyword hit rate: average fraction of expected keywords found in results
        hit_scores = []
        for r in results:
            keywords = r.get("expected_keywords", [])
            if not keywords:
                continue
            context = r["retrieved_context"].lower()
            hits = sum(1 for kw in keywords if kw.lower() in context)
            hit_scores.append(hits / len(keywords))

        keyword_hit_rate = sum(hit_scores) / len(hit_scores) if hit_scores else 0

        # Per-category breakdown
        categories: dict[str, list[float]] = {}
        for r, score in zip(
            results, hit_scores if hit_scores else [0] * total, strict=False
        ):
            cat = r.get("category", "unknown")
            categories.setdefault(cat, []).append(score)

        category_scores = {
            cat: round(sum(s) / len(s), 4) for cat, s in categories.items()
        }

        return {
            "metrics": {
                "retrieval_rate": round(retrieval_rate, 4),
                "keyword_hit_rate": round(keyword_hit_rate, 4),
                "category_scores": category_scores,
            },
            "sample_count": total,
            "status": "fallback",
        }

    def _compute_retrieval_metrics(self, results: list[dict]) -> dict[str, Any]:
        """Compute recall@k / MRR / citation hit style metrics when ids exist."""
        total_with_ids = 0
        recall_hits = {1: 0, 3: 0, 5: 0}
        reciprocal_ranks: list[float] = []
        keyword_recall_at_5: list[float] = []

        for result in results:
            items = result.get("retrieved_items") or []
            expected_ids = {str(x) for x in result.get("expected_doc_ids") or []}
            if expected_ids:
                total_with_ids += 1
                ranks = []
                for idx, item in enumerate(items, start=1):
                    item_id = str(
                        item.get("id")
                        or item.get("document_id")
                        or item.get("doc_id")
                        or item.get("source_id")
                        or ""
                    )
                    if item_id in expected_ids:
                        ranks.append(idx)
                for k in recall_hits:
                    if any(rank <= k for rank in ranks):
                        recall_hits[k] += 1
                reciprocal_ranks.append(1 / min(ranks) if ranks else 0)

            keywords = [str(k).lower() for k in result.get("expected_keywords") or []]
            if keywords:
                top5_text = "\n".join(str(i.get("text") or i) for i in items[:5]).lower()
                keyword_recall_at_5.append(
                    sum(1 for kw in keywords if kw in top5_text) / len(keywords)
                )

        metrics: dict[str, Any] = {
            "keyword_recall_at_5": round(
                sum(keyword_recall_at_5) / len(keyword_recall_at_5), 4
            )
            if keyword_recall_at_5
            else 0,
        }
        if total_with_ids:
            metrics.update(
                {
                    "recall_at_1": round(recall_hits[1] / total_with_ids, 4),
                    "recall_at_3": round(recall_hits[3] / total_with_ids, 4),
                    "recall_at_5": round(recall_hits[5] / total_with_ids, 4),
                    "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4),
                }
            )
        return {"metrics": metrics, "sample_count": len(results)}


rag_evaluator = RAGEvaluator()
