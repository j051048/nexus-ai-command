"""Compile tenant-scoped enterprise evidence into an artifact-ready packet."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.agent.artifact_contract import ArtifactSpec
from app.agent.scientific_writing_skills import enrich_artifact_spec
from app.agent.state import AgentConfig
from app.services.agent_evidence_service import (
    EvidencePacket,
    EvidenceRecord,
    retrieve_agent_evidence,
)


def _document_excerpt(document: dict[str, Any]) -> str:
    extracted = document.get("extracted_data") or {}
    if isinstance(extracted, dict):
        for key in ("full_text_context", "content", "text", "summary"):
            if extracted.get(key):
                return str(extracted[key])
    return str(extracted or "")


def _split_excerpt(value: str, limit: int = 1400) -> list[str]:
    paragraphs = [
        item.strip() for item in value.replace("\r", "").split("\n") if item.strip()
    ]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 1 > limit:
            chunks.append(current)
            current = ""
        current = f"{current}\n{paragraph}".strip()
    if current:
        chunks.append(current)
    if not chunks and value.strip():
        chunks = [value[index : index + limit] for index in range(0, len(value), limit)]
    return chunks[:12]


def _prompt_context(records: list[EvidenceRecord]) -> str:
    blocks = []
    for record in records[:18]:
        blocks.append(
            f"[{record.citation_id}] {record.title} | type={record.doc_type} | "
            f"version={record.source_version or 'unknown'} | purpose={','.join(record.purposes)}\n"
            f"{record.excerpt[:1400]}"
        )
    return "\n\n---\n\n".join(blocks)[:18000]


async def compile_artifact_evidence(
    *,
    query: str,
    spec: ArtifactSpec | dict[str, Any],
    organization_id: str,
    user_id: str,
    db: Any,
    selected_document_ids: list[str] | None = None,
) -> EvidencePacket:
    """Merge semantic RAG with explicitly selected enterprise documents.

    Explicit documents are split into independently citable passages. This is
    important for comprehensive manuals where one file legitimately covers
    several writing topics without pretending one repeated chunk is six facts.
    """

    spec = enrich_artifact_spec(spec)
    packet = await retrieve_agent_evidence(
        query=query,
        config=AgentConfig(
            user_id=user_id,
            org_id=organization_id,
            user_role="employee",
            rag_inject_limit=6,
        ),
        artifact_spec=spec,
        db=db,
    )
    records = list(packet.records)
    explicit_topics: set[str] = set()
    ids = list(
        dict.fromkeys(str(item) for item in (selected_document_ids or []) if item)
    )[:20]
    if ids:
        result = (
            await db.table("documents")
            .select(
                "id,name,doc_type,review_status,source_version,valid_until,quality_score,extracted_data"
            )
            .eq("organization_id", organization_id)
            .in_("id", ids)
            .execute()
        )
        for document in result.data or []:
            if document.get("review_status") in {"rejected", "expired"}:
                continue
            chunks = _split_excerpt(_document_excerpt(document))
            for index, excerpt in enumerate(chunks):
                purpose = (
                    spec.retrieval_topics[index % len(spec.retrieval_topics)]
                    if spec.retrieval_topics
                    else query
                )
                explicit_topics.add(purpose)
                records.append(
                    EvidenceRecord(
                        document_id=str(document.get("id")),
                        chunk_id=f"selected-{index + 1}",
                        title=str(document.get("name") or "企业资料"),
                        source=str(document.get("name") or "企业资料"),
                        doc_type=str(document.get("doc_type") or "other"),
                        excerpt=excerpt,
                        score=1.0,
                        source_version=document.get("source_version"),
                        valid_until=document.get("valid_until"),
                        review_status=document.get("review_status"),
                        purposes=[purpose],
                    )
                )

    deduplicated: list[EvidenceRecord] = []
    seen: set[tuple[str, str]] = set()
    for record in sorted(records, key=lambda item: item.score, reverse=True):
        key = (record.document_id, record.chunk_id)
        if key in seen or not record.excerpt.strip():
            continue
        seen.add(key)
        deduplicated.append(record)
    deduplicated = deduplicated[:18]

    covered = set(packet.covered_topics) | explicit_topics
    topics = list(spec.retrieval_topics or packet.topics or [query])
    missing = [topic for topic in topics if topic not in covered]
    coverage = 1.0 if not topics else (len(topics) - len(missing)) / len(topics)
    minimum = min(3, len(topics)) if spec.requires_quality_gate and topics else 1
    sufficient = (
        len(deduplicated) >= minimum
        and coverage >= spec.min_evidence_coverage
        and not missing
    )
    fingerprint_source = json.dumps(
        [
            (item.document_id, item.chunk_id, item.source_version)
            for item in deduplicated
        ],
        ensure_ascii=False,
    )
    return EvidencePacket(
        records=deduplicated,
        graph_context=packet.graph_context,
        topics=topics,
        covered_topics=[topic for topic in topics if topic in covered],
        missing_topics=missing,
        coverage=round(coverage, 4),
        minimum_record_count=minimum,
        sufficient=sufficient,
        prompt_context=_prompt_context(deduplicated),
        fingerprint=hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest(),
    )
