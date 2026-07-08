"""Shared retrieval safety helpers for vector, graph and GraphRAG flows."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_FETCH_K = 4096


@dataclass(frozen=True)
class MetadataFilter:
    """Parameterized metadata filter snippet plus values."""

    snippet: str
    params: dict[str, Any]


def validate_identifier(value: str, *, field_name: str = "identifier") -> str:
    """Validate an identifier before interpolating it into query text."""

    if not value or not IDENTIFIER_PATTERN.match(value):
        raise ValueError(
            f"Invalid {field_name}: {value!r}. Use letters, digits and underscores; "
            "the first character cannot be a digit."
        )
    return value


def construct_metadata_filter(
    filters: dict[str, Any] | None,
    *,
    alias: str = "n",
    param_prefix: str = "filter_param",
) -> MetadataFilter:
    """Build a parameterized equality filter for metadata values."""

    validate_identifier(alias, field_name="query alias")
    if not filters:
        return MetadataFilter("", {})

    snippets: list[str] = []
    params: dict[str, Any] = {}
    for index, (key, value) in enumerate(filters.items()):
        validate_identifier(key, field_name="metadata filter key")
        param_name = f"{param_prefix}_{index}"
        snippets.append(f"{alias}.`{key}` = ${param_name}")
        params[param_name] = value
    return MetadataFilter(" AND ".join(snippets), params)


def require_org_scope(
    filters: dict[str, Any] | None, org_id: str | None
) -> dict[str, Any]:
    """Ensure every retrieval filter carries tenant scope."""

    if not org_id:
        raise ValueError("GraphRAG retrieval requires org_id for tenant isolation.")
    scoped = dict(filters or {})
    scoped.setdefault("organization_id", org_id)
    return scoped


def normalize_scores(
    items: Iterable[dict[str, Any]],
    *,
    score_key: str = "score",
    lower_is_better: bool = False,
) -> list[dict[str, Any]]:
    """Normalize raw scores into ``normalized_score`` in the [0, 1] range."""

    rows = [dict(item) for item in items]
    if not rows:
        return []
    scores = [float(row.get(score_key, 0.0) or 0.0) for row in rows]
    minimum = min(scores)
    maximum = max(scores)
    span = maximum - minimum
    for row, score in zip(rows, scores, strict=False):
        normalized = 1.0 if span == 0 else (score - minimum) / span
        row["normalized_score"] = 1.0 - normalized if lower_is_better else normalized
    return rows


def next_fetch_k(
    *,
    current_fetch_k: int,
    requested_k: int,
    observed_count: int,
    previous_count: int | None,
    cap: int = MAX_FETCH_K,
) -> int | None:
    """Escalate fetch size when an index returns fewer live rows than requested."""

    if observed_count >= requested_k:
        return None
    if observed_count == previous_count:
        return None
    if current_fetch_k >= cap:
        return None
    return min(max(current_fetch_k * 4, 16), cap)


def _char_bigrams(text: str) -> set[str]:
    normalized = text.lower().strip()
    if not normalized:
        return set()
    if len(normalized) == 1:
        return {normalized}
    return {normalized[index : index + 2] for index in range(len(normalized) - 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def mmr_select_texts(
    items: list[dict[str, Any]],
    *,
    text_key: str = "text",
    score_key: str = "score",
    limit: int = 8,
    lambda_mult: float = 0.7,
) -> list[dict[str, Any]]:
    """Select relevant but non-duplicative text items using MMR."""

    if len(items) <= 1:
        return items[:limit]

    normalized = normalize_scores(items, score_key=score_key)
    tokens = [_char_bigrams(str(item.get(text_key, ""))) for item in normalized]
    candidates = list(range(len(normalized)))
    selected: list[int] = []

    while candidates and len(selected) < min(limit, len(normalized)):
        best_index = -1
        best_value = -math.inf
        for index in candidates:
            relevance = float(normalized[index].get("normalized_score", 0.0))
            max_similarity = (
                max(_jaccard(tokens[index], tokens[chosen]) for chosen in selected)
                if selected
                else 0.0
            )
            value = lambda_mult * relevance - (1 - lambda_mult) * max_similarity
            if value > best_value:
                best_value = value
                best_index = index
        selected.append(best_index)
        candidates.remove(best_index)

    return [normalized[index] for index in selected]
