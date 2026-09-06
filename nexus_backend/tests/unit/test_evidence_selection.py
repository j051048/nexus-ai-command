from app.services.agent_evidence_service import EvidenceRecord
from app.services.artifact_evidence_compiler import _prompt_context, _split_excerpt
from app.services.artifact_quality_service import _heading_present
from app.services.evidence_selection import select_evidence


def record(document, index, purpose):
    return EvidenceRecord(document_id=document, chunk_id=str(index), title=document,
                          excerpt=f"{document}-{index}:" + "evidence " * 200,
                          score=1, purposes=[purpose])


def test_topic_and_source_diversity_survive_long_document():
    rows = [record("manual", index, "parameters") for index in range(20)]
    rows += [record("service", 0, "warranty"), record("case", 0, "experience")]
    kept = select_evidence(rows, ["parameters", "warranty", "experience"], max_records=6)
    assert {item.document_id for item in kept} == {"manual", "service", "case"}
    assert all(item.citation_id in _prompt_context(kept) for item in kept)
    assert len(_prompt_context(kept)) < 28000


def test_duplicate_excerpt_merges_purposes_without_mutating_input():
    first = record("manual", 0, "parameters")
    second = first.model_copy(update={"purposes": ["warranty"]})
    kept = select_evidence([first, second], ["parameters", "warranty"])
    assert len(kept) == 1
    assert kept[0].purposes == ["parameters", "warranty"]
    assert first.purposes == ["parameters"]


def test_long_unpunctuated_paragraph_has_bounded_chunks():
    assert max(map(len, _split_excerpt("x" * 12000))) <= 1600


def test_body_mentions_are_not_section_headings():
    assert not _heading_present("# Solution\nThis discusses售后服务", "售后服务")
    assert _heading_present("## 售后服务\nBody", "售后服务")
