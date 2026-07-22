"""Compile tenant-scoped enterprise evidence into an artifact-ready packet."""

from __future__ import annotations

import hashlib
import json
import re
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


_HEADING_RE = re.compile(
    r"^(?:#{1,6}\s+|[一二三四五六七八九十]+[、.．]|\d+(?:\.\d+){0,2}[、.．\s])"
)

_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "客户行业场景与样品": ("客户", "行业", "应用", "场景", "样品", "检测对象", "需求"),
    "产品型号参数和检测能力": (
        "型号",
        "参数",
        "量程",
        "精度",
        "检出限",
        "通道",
        "检测",
        "性能",
    ),
    "适用标准政策": (
        "标准",
        "政策",
        "法规",
        "规范",
        "办法",
        "条例",
        "国标",
        "行业标准",
    ),
    "竞品参数": ("竞品", "对比", "同类", "进口", "替代", "差异", "优势"),
    "授权客户案例": ("案例", "客户", "项目", "应用", "验收", "部署", "用户"),
    "安装培训维保条款": (
        "安装",
        "培训",
        "维保",
        "售后",
        "服务",
        "保修",
        "校准",
        "响应",
    ),
    "招标强制条款和评分项": ("招标", "评分", "强制", "必须", "否决", "条款", "响应"),
    "资质证书": ("资质", "证书", "认证", "专利", "授权", "检测报告"),
    "交付验收售后条款": ("交付", "验收", "售后", "培训", "保修", "响应", "服务"),
    "我方产品参数": ("我方", "产品", "型号", "参数", "性能", "配置"),
    "竞品公开参数": ("竞品", "公开", "型号", "参数", "性能", "品牌"),
    "现行政策原文": ("政策", "法规", "原文", "条款", "发布", "实施"),
    "维护校准规范": ("维护", "保养", "校准", "计量", "周期", "规程"),
    "原始数据与质量控制": (
        "原始数据",
        "质控",
        "质量控制",
        "空白",
        "平行",
        "回收率",
        "重复性",
    ),
}

_DOCUMENT_FIELDS = (
    "id,name,doc_type,review_status,source_version,valid_until,quality_score,"
    "extracted_data"
)


def _requested_filename_stems(query: str) -> list[str]:
    matches = re.findall(
        r"([^\n\r\"“”<>|]{4,120}?)\.(?:docx?|pdf|xlsx?|pptx?)\b",
        str(query or ""),
        re.I,
    )
    stems: list[str] = []
    for match in matches:
        stem = re.sub(r"^[，。；：、\s]+|[，。；：、\s]+$", "", match)
        stem = re.sub(r"^(?:参考|基于|使用|按照|调用|读取)", "", stem).strip()
        if len(stem) >= 4:
            stems.append(stem[-80:])
    return list(dict.fromkeys(stems))[:4]


async def _load_explicit_documents(
    *,
    db: Any,
    organization_id: str,
    selected_document_ids: list[str],
    query: str,
) -> list[dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    if selected_document_ids:
        result = (
            await db.table("documents")
            .select(_DOCUMENT_FIELDS)
            .eq("organization_id", organization_id)
            .in_("id", selected_document_ids)
            .execute()
        )
        documents.update(
            {
                str(item.get("id")): item
                for item in (result.data or [])
                if item.get("id")
            }
        )
    for stem in _requested_filename_stems(query):
        try:
            result = (
                await db.table("documents")
                .select(_DOCUMENT_FIELDS)
                .eq("organization_id", organization_id)
                .ilike("name", f"%{stem}%")
                .limit(4)
                .execute()
            )
        except (AttributeError, TypeError):
            continue
        documents.update(
            {
                str(item.get("id")): item
                for item in (result.data or [])
                if item.get("id")
            }
        )
    return list(documents.values())


def _split_excerpt(value: str, limit: int = 1600) -> list[str]:
    raw_paragraphs = [
        item.strip() for item in value.replace("\r", "").split("\n") if item.strip()
    ]
    paragraphs: list[str] = []
    for paragraph in raw_paragraphs:
        if len(paragraph) <= limit:
            paragraphs.append(paragraph)
            continue
        sentences = re.split(r"(?<=[。！？；])", paragraph)
        current_sentence_block = ""
        for sentence in sentences:
            if (
                current_sentence_block
                and len(current_sentence_block) + len(sentence) > limit
            ):
                paragraphs.append(current_sentence_block)
                current_sentence_block = ""
            current_sentence_block += sentence
        if current_sentence_block:
            paragraphs.append(current_sentence_block)
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        starts_section = bool(_HEADING_RE.match(paragraph))
        if current and (
            len(current) + len(paragraph) + 1 > limit
            or (starts_section and len(current) >= 420)
        ):
            chunks.append(current)
            current = ""
        current = f"{current}\n{paragraph}".strip()
    if current:
        chunks.append(current)
    if not chunks and value.strip():
        chunks = [value[index : index + limit] for index in range(0, len(value), limit)]
    return chunks[:20]


def _topic_score(topic: str, excerpt: str, title: str) -> int:
    value = f"{title}\n{excerpt}".lower()
    keywords = _TOPIC_KEYWORDS.get(topic)
    if not keywords:
        keywords = tuple(
            token
            for token in re.split(r"[与和及、/\s]+", topic)
            if len(token.strip()) >= 2
        )
    return sum(2 if keyword in title else 1 for keyword in keywords if keyword in value)


def _match_topics(
    topics: list[str], excerpt: str, title: str, *, limit: int = 3
) -> list[str]:
    ranked = sorted(
        ((topic, _topic_score(topic, excerpt, title)) for topic in topics),
        key=lambda item: item[1],
        reverse=True,
    )
    return [topic for topic, score in ranked if score > 0][:limit]


def _prompt_context(records: list[EvidenceRecord]) -> str:
    blocks = [
        "[资料分解索引] 以下内容已经按章节和用途拆分。写作时先比较、归类和消除重复，"
        "再引用证据；不得把资料标题或检索标记直接复制成正文。"
    ]
    for record in records[:24]:
        blocks.append(
            f"[{record.citation_id}] {record.title} | type={record.doc_type} | "
            f"version={record.source_version or 'unknown'} | purpose={','.join(record.purposes)}\n"
            f"{record.excerpt[:1400]}"
        )
    return "\n\n---\n\n".join(blocks)[:28000]


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
    topics = list(spec.retrieval_topics or [query])
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
    explicit_documents = await _load_explicit_documents(
        db=db,
        organization_id=organization_id,
        selected_document_ids=ids,
        query=query,
    )
    if explicit_documents:
        for document in explicit_documents:
            if document.get("review_status") in {"rejected", "expired"}:
                continue
            chunks = _split_excerpt(_document_excerpt(document))
            title = str(document.get("name") or "企业资料")
            for index, excerpt in enumerate(chunks):
                purposes = _match_topics(topics, excerpt, title)
                explicit_topics.update(purposes)
                records.append(
                    EvidenceRecord(
                        document_id=str(document.get("id")),
                        chunk_id=f"selected-{index + 1}",
                        title=title,
                        source=title,
                        doc_type=str(document.get("doc_type") or "other"),
                        excerpt=excerpt,
                        score=1.0,
                        source_version=document.get("source_version"),
                        valid_until=document.get("valid_until"),
                        review_status=document.get("review_status"),
                        purposes=purposes or ["指定企业资料"],
                    )
                )

    deduplicated: list[EvidenceRecord] = []
    seen: set[tuple[str, str]] = set()
    seen_content: set[str] = set()
    for record in sorted(records, key=lambda item: item.score, reverse=True):
        key = (record.document_id, record.chunk_id)
        content_hash = hashlib.sha256(
            re.sub(r"\s+", "", record.excerpt).encode("utf-8")
        ).hexdigest()
        if key in seen or content_hash in seen_content or not record.excerpt.strip():
            continue
        seen.add(key)
        seen_content.add(content_hash)
        deduplicated.append(record)
    deduplicated = deduplicated[:24]

    covered = set(packet.covered_topics) | explicit_topics
    topics = list(spec.retrieval_topics or packet.topics or [query])
    missing = [topic for topic in topics if topic not in covered]
    coverage = 1.0 if not topics else (len(topics) - len(missing)) / len(topics)
    minimum = min(4, len(topics)) if spec.requires_quality_gate and topics else 1
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
