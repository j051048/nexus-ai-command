"""Query-aware memory retrieval policy for predictable latency and cost."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryContextPolicy:
    sources: tuple[str, ...]
    token_budget: int


_GRAPH_TERMS = ("客户", "项目", "合同", "仪器", "设备", "校准", "维修", "关系", "关联")
_HISTORY_TERMS = ("上次", "之前", "历史", "过去", "曾经", "复盘")
_ADVICE_TERMS = ("建议", "下一步", "怎么", "策略", "方案", "计划")
_REASONING_TERMS = ("为什么", "原因", "分析", "比较", "权衡", "推演")


def choose_memory_context_policy(
    query: str, complexity: str | None = None
) -> MemoryContextPolicy:
    """Select only memory planes that can materially help the request."""
    text = (query or "").strip().lower()
    complexity = (complexity or "").lower()
    sources = ["l1", "l2"]
    if any(term in text for term in _GRAPH_TERMS + _ADVICE_TERMS):
        sources.append("org")
    if any(term in text for term in _GRAPH_TERMS):
        sources.append("kg")
    if any(term in text for term in _ADVICE_TERMS):
        sources.append("patterns")
    if any(term in text for term in _HISTORY_TERMS):
        sources.append("episodic")
    if complexity in {"complex", "high", "wbs"} or any(
        term in text for term in _REASONING_TERMS
    ):
        sources.append("reasoning")
    budget = 900 if len(text) <= 24 and len(sources) == 2 else 1400
    if len(sources) > 4:
        budget = 1800
    return MemoryContextPolicy(tuple(sources), budget)
