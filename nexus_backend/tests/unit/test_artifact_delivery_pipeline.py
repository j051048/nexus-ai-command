import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from docx import Document

from app.agent.artifact_contract import (
    ArtifactAudience,
    ArtifactSpec,
    ArtifactType,
    infer_artifact_spec,
)
from app.agent.scientific_writing_skills import enrich_artifact_spec
from app.services.agent_evidence_service import EvidencePacket, EvidenceRecord
from app.services.artifact_content_sanitizer import (
    contains_internal_trace_markers,
    sanitize_artifact_content,
)
from app.services.artifact_docx_renderer import (
    render_artifact_docx,
    render_artifact_pdf,
    render_artifact_xlsx,
)
from app.services.artifact_evidence_compiler import compile_artifact_evidence
from app.services.artifact_generation_service import generate_artifact
from app.services.artifact_quality_service import evaluate_text_artifact


def _packet() -> dict:
    return {
        "records": [
            {
                "document_id": "doc-1",
                "chunk_id": "chunk-1",
                "title": "FD-F 产品手册",
                "source_version": "2026.2",
                "excerpt": "产品参数已经过企业审核。",
            }
        ],
        "coverage": 1.0,
        "sufficient": True,
        "missing_topics": [],
    }


def test_sanitizer_removes_trace_deduplicates_and_humanizes_sources():
    repeated = "这是一段需要去重的企业资料说明，内容足够长以便识别重复段落。"
    raw = (
        "[企业资料检索结果]\n\n"
        "tool_name: loadknowledge\n\n"
        f"{repeated}\n\n{repeated}\n\n"
        "核心参数已核验。[EVID:doc-1:chunk-1]"
    )

    result = sanitize_artifact_content(raw, _packet())

    assert "企业资料检索结果" not in result.content
    assert "tool_name" not in result.content
    assert result.content.count(repeated) == 1
    assert "[来源 1]" in result.content
    assert result.source_notes[0]["title"] == "FD-F 产品手册"
    assert result.duplicate_paragraph_count == 1


def test_professional_renderers_share_clean_canonical_content():
    artifact = {
        "title": "FD-F 多功能食品安全检测仪升级方案",
        "artifact_code": "ART-20260722-TEST",
        "artifact_label": "客户解决方案",
        "version_number": 2,
        "approval_status": "approved",
        "quality_score": 93,
        "content_markdown": (
            "# FD-F 多功能食品安全检测仪升级方案\n\n"
            "## 项目背景与客户目标\n企业需要完成设备升级。[EVID:doc-1:chunk-1]\n\n"
            "## 推荐配置\n| 模块 | 说明 |\n| --- | --- |\n| 主机 | 待核验 |"
        ),
    }

    docx = render_artifact_docx(artifact, _packet(), {"name": "飞达科技"})
    pdf = render_artifact_pdf(artifact, _packet(), {"name": "飞达科技"})
    xlsx = render_artifact_xlsx(artifact, _packet())

    document = Document(io.BytesIO(docx))
    all_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "资料来源" in all_text
    assert "[来源 1]" in all_text
    assert "EVID:" not in all_text
    assert len(document.tables) >= 2
    assert pdf.startswith(b"%PDF")
    assert xlsx.startswith(b"PK")


def test_quality_gate_blocks_internal_trace_and_unsupported_numbers():
    spec = enrich_artifact_spec(
        ArtifactSpec(
            artifact_type=ArtifactType.CUSTOMER_SOLUTION,
            audience=ArtifactAudience.CUSTOMER,
            strict_quality=True,
            external_delivery=True,
        )
    )
    text = "\n\n".join(
        f"## {title}\ntool_result: 原始结果，保证 100% 达标。"
        for title in spec.required_sections
    )

    quality = evaluate_text_artifact(text, spec, _packet())
    codes = {item["code"] for item in quality["findings"]}

    assert contains_internal_trace_markers(text)
    assert quality["ready"] is False
    assert {"internal_trace_leakage", "numeric_claims_unsupported"} <= codes


def test_delivery_golden_set_covers_five_instrument_families():
    dataset = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "evals"
            / "datasets"
            / "artifact_delivery_golden.json"
        ).read_text(encoding="utf-8")
    )

    assert len(dataset["cases"]) == 5
    for case in dataset["cases"]:
        spec = infer_artifact_spec(case["request"])
        assert spec.artifact_type.value == case["artifact_type"]
        assert spec.instrument_line == case["instrument_line"]


class _FakeQuery:
    def __init__(self, table: str, rows: dict[str, list[dict]]):
        self.table = table
        self.rows = rows
        self.pending = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def in_(self, *_args, **_kwargs):
        return self

    def insert(self, value):
        self.pending = value
        return self

    async def execute(self):
        if self.pending is not None:
            values = self.pending if isinstance(self.pending, list) else [self.pending]
            self.rows.setdefault(self.table, []).extend(values)
            return SimpleNamespace(data=values)
        return SimpleNamespace(data=self.rows.get(self.table, []))


class _FakeDB:
    def __init__(self, rows=None):
        self.rows = rows or {}

    def table(self, name):
        return _FakeQuery(name, self.rows)


@pytest.mark.asyncio
async def test_explicit_enterprise_document_is_split_into_citable_topics(monkeypatch):
    async def empty_retrieval(**_kwargs):
        return EvidencePacket(topics=[], covered_topics=[], missing_topics=[])

    monkeypatch.setattr(
        "app.services.artifact_evidence_compiler.retrieve_agent_evidence",
        empty_retrieval,
    )
    long_sections = "\n".join(
        f"章节 {index} " + ("企业核验资料" * 120) for index in range(1, 7)
    )
    db = _FakeDB(
        {
            "documents": [
                {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "name": "FD-F 完整产品方案.docx",
                    "doc_type": "product",
                    "review_status": "approved",
                    "source_version": "2026.2",
                    "extracted_data": {"full_text_context": long_sections},
                }
            ]
        }
    )
    spec = enrich_artifact_spec(
        ArtifactSpec(
            artifact_type=ArtifactType.CUSTOMER_SOLUTION,
            strict_quality=True,
            external_delivery=True,
        )
    )

    packet = await compile_artifact_evidence(
        query="生成食品安全检测仪升级方案",
        spec=spec,
        organization_id="org-1",
        user_id="user-1",
        db=db,
        selected_document_ids=["11111111-1111-4111-8111-111111111111"],
    )

    assert len(packet.records) >= 6
    assert packet.coverage == 1.0
    assert packet.sufficient is True
    assert "FD-F 完整产品方案.docx" in packet.prompt_context


@pytest.mark.asyncio
async def test_generation_pipeline_persists_version_evidence_and_quality(monkeypatch):
    spec = enrich_artifact_spec(
        ArtifactSpec(
            artifact_type=ArtifactType.CUSTOMER_SOLUTION,
            strict_quality=True,
            external_delivery=True,
        )
    )
    records = [
        EvidenceRecord(
            document_id=f"doc-{index}",
            chunk_id=f"chunk-{index}",
            title=f"企业资料 {index}",
            excerpt="已核验的产品、交付与服务事实。",
            score=1.0,
            source_version="2026.2",
            purposes=[topic],
        )
        for index, topic in enumerate(spec.retrieval_topics, 1)
    ]
    packet = EvidencePacket(
        records=records,
        topics=spec.retrieval_topics,
        covered_topics=spec.retrieval_topics,
        coverage=1.0,
        minimum_record_count=3,
        sufficient=True,
        prompt_context="\n".join(
            f"[{item.citation_id}] {item.excerpt}" for item in records
        ),
        fingerprint="golden-evidence",
    )

    async def fake_compile(**_kwargs):
        return packet

    sections = [
        {
            "title": title,
            "content": f"{title}已经依据企业资料完成核验，并明确给出实施边界和后续行动。",
            "evidence_refs": [records[index % len(records)].citation_id],
        }
        for index, title in enumerate(spec.required_sections)
    ]

    async def fake_chat(**_kwargs):
        return SimpleNamespace(
            content=json.dumps(
                {
                    "title": "食品安全检测仪升级换代整体方案",
                    "executive_summary": "本方案面向食品安全检测能力升级，所有事实均来自企业资料。",
                    "sections": sections,
                    "verification_items": ["最终报价由负责人确认"],
                },
                ensure_ascii=False,
            ),
            finish_reason="stop",
            model_code="deepseek-v4-flash",
            usage={"total_tokens": 1200},
        )

    async def ignore_quality_event(**_kwargs):
        return None

    monkeypatch.setattr(
        "app.services.artifact_generation_service.compile_artifact_evidence",
        fake_compile,
    )
    monkeypatch.setattr(
        "app.services.artifact_generation_service.llm_gateway.chat", fake_chat
    )
    monkeypatch.setattr(
        "app.services.artifact_generation_service.persist_artifact_quality_event",
        ignore_quality_event,
    )
    db = _FakeDB()

    result = await generate_artifact(
        db=db,
        organization_id="11111111-1111-4111-8111-111111111111",
        user_id="22222222-2222-4222-8222-222222222222",
        original_request="给客户生成食品安全检测仪升级解决方案",
        source_content="已有聊天草稿",
        artifact_type=ArtifactType.CUSTOMER_SOLUTION,
        audience=ArtifactAudience.CUSTOMER,
        review_confirmed=True,
    )

    assert result["quality"]["ready"] is True
    assert result["approval_status"] == "approved"
    assert len(db.rows["artifacts"]) == 1
    assert len(db.rows["artifact_versions"]) == 1
    assert len(db.rows["artifact_evidence_links"]) == len(records)
