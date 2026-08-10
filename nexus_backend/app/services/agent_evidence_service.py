"""Section-aware, tenant-scoped evidence retrieval for Agent artifacts."""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from pydantic import BaseModel, Field

from app.agent.artifact_contract import ArtifactSpec
from app.agent.scientific_writing_skills import enrich_artifact_spec


class EvidenceRecord(BaseModel):
    document_id: str
    chunk_id: str
    title: str = "enterprise_knowledge"
    source: str = "enterprise_knowledge"
    doc_type: str = "other"
    excerpt: str = ""
    score: float = 0.0
    source_version: str | None = None
    valid_until: str | None = None
    review_status: str | None = None
    purposes: list[str] = Field(default_factory=list)

    @property
    def citation_id(self) -> str:
        return f"EVID:{self.document_id}:{self.chunk_id}"


class EvidencePacket(BaseModel):
    schema_version: str = "agent-evidence.v1"
    records: list[EvidenceRecord] = Field(default_factory=list)
    graph_context: str = ""
    topics: list[str] = Field(default_factory=list)
    covered_topics: list[str] = Field(default_factory=list)
    missing_topics: list[str] = Field(default_factory=list)
    coverage: float = 0.0
    minimum_record_count: int = 0
    sufficient: bool = False
    prompt_context: str = ""
    fingerprint: str = ""


def build_retrieval_topics(
    query: str, spec: ArtifactSpec | dict[str, Any]
) -> list[str]:
    spec = enrich_artifact_spec(spec)
    topics = list(spec.retrieval_topics)
    if not topics:
        topics = [query]
    # Skill topics already execute with the original query as context.  Adding
    # the raw query as another fan-out would spend one search while truncating
    # the last required topic for six-topic solution skills.
    return list(dict.fromkeys(topic.strip() for topic in topics if topic.strip()))[:6]


def _format_prompt_context(records: list[EvidenceRecord], graph_context: str) -> str:
    parts: list[str] = []
    for record in records[:12]:
        metadata = [record.title]
        if record.source_version:
            metadata.append(f"version={record.source_version}")
        if record.valid_until:
            metadata.append(f"valid_until={record.valid_until}")
        purposes = ", ".join(record.purposes[:3])
        parts.append(
            f"[{record.citation_id}] {' | '.join(metadata)} | purpose={purposes}\n"
            f"{record.excerpt[:900]}"
        )
    if graph_context:
        parts.append("[BUSINESS_GRAPH]\n" + graph_context[:2000])
    return "\n\n---\n\n".join(parts)[:10000]


async def retrieve_agent_evidence(
    *,
    query: str,
    config: Any,
    artifact_spec: ArtifactSpec | dict[str, Any],
    db: Any | None = None,
) -> EvidencePacket:
    """Retrieve auditable evidence records with bounded parallel fan-out."""

    spec = enrich_artifact_spec(artifact_spec)
    org_id = getattr(config, "org_id", None)
    user_id = getattr(config, "user_id", None)
    if not org_id or not user_id:
        return EvidencePacket(topics=build_retrieval_topics(query, spec))
    topics = build_retrieval_topics(query, spec)
    from app.services.vector_service import vector_service

    async def _search(topic: str) -> tuple[str, list[dict[str, Any]]]:
        rows = await vector_service.search_evidence(
            query=f"{query}\n检索目的：{topic}" if topic != query else query,
            user_id=user_id,
            limit=max(2, min(getattr(config, "rag_inject_limit", 4), 6)),
            org_id=org_id,
        )
        return topic, rows

    raw_results = await asyncio.gather(
        *[_search(topic) for topic in topics], return_exceptions=True
    )
    merged: dict[tuple[str, str], EvidenceRecord] = {}
    covered_topics: list[str] = []
    for result in raw_results:
        if isinstance(result, Exception):
            continue
        topic, rows = result
        if rows:
            covered_topics.append(topic)
        for row in rows:
            document_id = str(row.get("document_id") or row.get("id") or "")
            chunk_id = str(row.get("chunk_id") or row.get("id") or "")
            if not document_id or not chunk_id:
                continue
            key = (document_id, chunk_id)
            if key not in merged:
                merged[key] = EvidenceRecord(
                    document_id=document_id,
                    chunk_id=chunk_id,
                    title=str(
                        row.get("name")
                        or row.get("title")
                        or row.get("source")
                        or "enterprise_knowledge"
                    ),
                    source=str(row.get("source") or "enterprise_knowledge"),
                    doc_type=str(row.get("doc_type") or "other"),
                    excerpt=str(row.get("excerpt") or row.get("content") or ""),
                    score=float(row.get("score") or 0),
                    source_version=row.get("source_version"),
                    valid_until=(
                        str(row.get("valid_until")) if row.get("valid_until") else None
                    ),
                    review_status=row.get("review_status"),
                    purposes=[topic],
                )
            elif topic not in merged[key].purposes:
                merged[key].purposes.append(topic)

    records = sorted(merged.values(), key=lambda item: item.score, reverse=True)[:12]
    graph_context = ""
    if db is not None and spec.requires_quality_gate:
        try:
            from app.services.graph_rag_retrieval_service import (
                build_graph_rag_context_packet,
            )

            graph_packet = await build_graph_rag_context_packet(
                db,
                query=query,
                org_id=org_id,
                user_id=user_id,
                role=getattr(config, "user_role", None),
                limit=6,
            )
            graph_context = graph_packet.prompt_context
        except Exception:  # broad-except: intentional
            graph_context = ""

    missing = [topic for topic in topics if topic not in covered_topics]
    coverage = len(covered_topics) / len(topics) if topics else 0.0
    prompt_context = _format_prompt_context(records, graph_context)
    fingerprint_payload = "|".join(
        [
            f"{item.document_id}:{item.chunk_id}:{item.source_version or ''}"
            for item in records
        ]
    )
    minimum_record_count = (
        min(3, len(topics)) if spec.requires_quality_gate and topics else 1
    )
    return EvidencePacket(
        records=records,
        graph_context=graph_context,
        topics=topics,
        covered_topics=covered_topics,
        missing_topics=missing,
        coverage=round(coverage, 4),
        minimum_record_count=minimum_record_count,
        sufficient=(
            len(records) >= minimum_record_count
            and coverage >= spec.min_evidence_coverage
        ),
        prompt_context=prompt_context,
        fingerprint=hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest(),
    )
