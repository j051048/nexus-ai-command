"""RAG 检索质量评估器

基于关键词匹配的简单检索模拟（不需要真实向量 DB），
计算 Recall@5, MRR, NDCG@5 三个指标。
"""

import math
import re
from typing import Any

from evals.eval_metrics import EvalDimension, EvalResult


class RAGQualityEvaluator:
    """评估 RAG 检索质量：Recall@5, MRR, NDCG@5。"""

    dimension = EvalDimension.RAG_QUALITY

    async def evaluate(self, case: dict[str, Any]) -> EvalResult:
        query = case["query"]
        relevant_ids = set(case.get("relevant_doc_ids", []))
        corpus = case.get("corpus", [])

        if not corpus:
            return EvalResult(
                case_id=case["id"], dimension=self.dimension,
                passed=False, score=0.0, error="Empty corpus",
            )

        # Simple keyword-based retrieval simulation
        query_terms = set(_tokenize(query))
        scored_docs = []
        for doc in corpus:
            doc_terms = set(_tokenize(doc.get("content", "")))
            overlap = len(query_terms & doc_terms)
            score = overlap / max(len(query_terms | doc_terms), 1)
            scored_docs.append((doc["id"], score))

        scored_docs.sort(key=lambda x: -x[1])
        top_k = [doc_id for doc_id, _ in scored_docs[:5]]

        # No relevant documents expected
        if not relevant_ids:
            top_scores = [s for _, s in scored_docs[:3]]
            avg_top = sum(top_scores) / max(len(top_scores), 1)
            passed = avg_top < 0.3
            return EvalResult(
                case_id=case["id"], dimension=self.dimension,
                passed=passed, score=1.0 if passed else 0.0,
                details={"recall_5": 0, "mrr": 0, "ndcg_5": 0, "retrieved": top_k},
            )

        # Recall@5
        retrieved_relevant = relevant_ids & set(top_k)
        recall_5 = len(retrieved_relevant) / len(relevant_ids)

        # MRR
        mrr = 0.0
        for rank, doc_id in enumerate(top_k, 1):
            if doc_id in relevant_ids:
                mrr = 1.0 / rank
                break

        # NDCG@5
        dcg = sum(
            (1.0 if top_k[i] in relevant_ids else 0.0) / math.log2(i + 2)
            for i in range(min(5, len(top_k)))
        )
        ideal = sorted([1.0] * len(relevant_ids) + [0.0] * max(0, 5 - len(relevant_ids)), reverse=True)[:5]
        idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
        ndcg_5 = dcg / idcg if idcg > 0 else 0.0

        composite = recall_5 * 0.4 + mrr * 0.3 + ndcg_5 * 0.3

        return EvalResult(
            case_id=case["id"],
            dimension=self.dimension,
            passed=composite >= 0.5,
            score=round(composite, 4),
            details={
                "recall_5": round(recall_5, 4),
                "mrr": round(mrr, 4),
                "ndcg_5": round(ndcg_5, 4),
                "retrieved": top_k,
                "relevant_found": list(retrieved_relevant),
            },
        )


def _tokenize(text: str) -> list[str]:
    """Simple Chinese+English tokenization."""
    tokens = []
    tokens.extend(re.findall(r"[a-zA-Z0-9]+", text.lower()))
    chinese = re.findall(r"[\u4e00-\u9fff]", text)
    tokens.extend(chinese)
    for i in range(len(chinese) - 1):
        tokens.append(chinese[i] + chinese[i + 1])
    return tokens
