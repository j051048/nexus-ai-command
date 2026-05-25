"""Context quality scoring and evidence-pack helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ContextQualityScore:
    provider: str
    relevance: float
    authority: float
    freshness: float
    permission_scope: str
    quality_score: float
    conflict_flag: bool = False
    evidence_ids: list[str] = field(default_factory=list)
    assessed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ContextQualityService:
    HIGH_AUTHORITY_PROVIDERS = {
        "business_context_graph",
        "KnowledgeBaseProvider",
        "知识库检索",
        "你与用户的历史对话",
    }

    def score_context_block(
        self,
        *,
        provider: str,
        text: str,
        query: str,
        org_id: str | None,
        user_id: str | None,
    ) -> ContextQualityScore:
        query_terms = {
            token.strip().lower()
            for token in query.replace("，", " ").replace(",", " ").split()
            if len(token.strip()) >= 2
        }
        lowered = text.lower()
        if query_terms:
            hits = sum(1 for term in query_terms if term in lowered)
            relevance = min(1.0, 0.35 + hits / max(len(query_terms), 1) * 0.65)
        else:
            relevance = 0.55 if text else 0

        authority = 0.9 if provider in self.HIGH_AUTHORITY_PROVIDERS else 0.7
        if "[业务知识图谱]" in text or "证据" in text:
            authority = min(1.0, authority + 0.08)

        freshness = 0.75
        if "updated_at" in text or "created_at" in text or "当前" in text:
            freshness = 0.88
        if "过期" in text or "expired" in text:
            freshness = 0.35

        permission_scope = "tenant_scoped" if org_id else "user_scoped"
        conflict_flag = any(
            marker in text for marker in ("冲突", "contradict", "不一致")
        )
        if conflict_flag:
            relevance = max(0, relevance - 0.15)

        quality_score = round(
            max(0, min(1, relevance * 0.45 + authority * 0.3 + freshness * 0.25)),
            4,
        )
        return ContextQualityScore(
            provider=provider,
            relevance=round(relevance, 4),
            authority=round(authority, 4),
            freshness=round(freshness, 4),
            permission_scope=permission_scope,
            quality_score=quality_score,
            conflict_flag=conflict_flag,
            evidence_ids=self.extract_evidence_ids(text, provider),
        )

    @staticmethod
    def extract_evidence_ids(text: str, provider: str) -> list[str]:
        evidence: list[str] = []
        for token in (
            "customer:",
            "lead:",
            "project:",
            "contract:",
            "approval:",
            "document:",
        ):
            start = 0
            while True:
                idx = text.find(token, start)
                if idx == -1:
                    break
                raw = text[idx : idx + 80].split()[0].strip("，。；;,)")
                if raw not in evidence:
                    evidence.append(raw)
                start = idx + len(token)
        if not evidence and text:
            evidence.append(f"{provider}:runtime")
        return evidence[:12]

    def build_evidence_pack(self, ledger: dict[str, Any]) -> dict[str, Any]:
        entries = ledger.get("entries") or []
        included = [entry for entry in entries if entry.get("included")]
        scores = [
            float(entry.get("quality_score") or 0)
            for entry in included
            if entry.get("quality_score") is not None
        ]
        evidence_ids: list[str] = []
        for entry in included:
            for evidence_id in entry.get("evidence_ids") or []:
                if evidence_id not in evidence_ids:
                    evidence_ids.append(evidence_id)
        return {
            "context_quality_score": (
                round(sum(scores) / len(scores), 4) if scores else 0
            ),
            "included_blocks": len(included),
            "evidence_ids": evidence_ids[:20],
            "conflict_count": sum(
                1 for entry in included if entry.get("conflict_flag")
            ),
            "permission_scopes": sorted(
                {
                    entry.get("permission_scope")
                    for entry in included
                    if entry.get("permission_scope")
                }
            ),
        }


context_quality_service = ContextQualityService()
