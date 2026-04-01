"""
Cohere Rerank integration for improved retrieval.

P0 Task: Reduce candidate set from 100 to 10 using Cohere Rerank.
"""

import logging
import os
from typing import List, Dict

logger = logging.getLogger(__name__)


def rerank_candidates(query: str, candidates: List[Dict], top_n: int = 10) -> List[Dict]:
    """
    Rerank candidates using Cohere Rerank API.

    Args:
        query: User query
        candidates: List of candidate documents with 'content' field
        top_n: Number of top results to return

    Returns:
        Reranked candidates
    """
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        logger.warning("[Cohere] API key not set, returning original candidates")
        return candidates[:top_n]

    try:
        import cohere

        co = cohere.Client(api_key)

        documents = [c.get("content", "") for c in candidates]

        results = co.rerank(
            query=query,
            documents=documents,
            top_n=top_n,
            model="rerank-english-v2.0",
        )

        reranked = []
        for result in results:
            idx = result.index
            if idx < len(candidates):
                reranked.append(candidates[idx])

        logger.info(f"[Cohere] Reranked {len(candidates)} → {len(reranked)}")
        return reranked

    except ImportError:
        logger.error("[Cohere] Library not installed: pip install cohere")
        return candidates[:top_n]
    except Exception as e:
        logger.error(f"[Cohere] Rerank failed: {e}")
        return candidates[:top_n]
