import pytest

from app.services.artifact_feedback_loop import (
    compute_artifact_diff,
    record_customer_outcome,
    record_learning_candidate,
    summarize_failure_modes,
)


def test_compute_artifact_diff_tracks_added_removed():
    original = "第一段\n第二段\n第三段\n"
    revised = "第一段\n修改后的第二段\n新增段落\n"
    diff = compute_artifact_diff(original, revised)
    assert diff["similarity"] > 0
    assert diff["paragraphs_removed"] >= 1
    assert diff["paragraphs_added"] >= 1


class _FakeDb:
    def __init__(self):
        self.records = []

    def table(self, name):
        self.current_table = name
        return self

    def select(self, *cols):
        return self

    def eq(self, *args):
        return self

    def gte(self, *args):
        return self

    def lt(self, *args):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self

    async def execute(self):
        return _FakeResult(self.records)

    def insert(self, payload):
        self.records = [payload]
        return self


class _FakeResult:
    def __init__(self, data):
        self.data = data


@pytest.mark.asyncio
async def test_record_learning_candidate_marks_review_candidate():
    db = _FakeDb()
    result = await record_learning_candidate(
        db,
        organization_id="org-1",
        user_id="user-1",
        artifact_id="artifact-1",
        artifact_version_id="version-1",
        change_type="accepted",
        rating=5,
        comment="ok",
        original_content="旧内容",
        revised_content="新内容更完整",
        quality_before={"score": 80, "ready": False},
        quality_after={"score": 92, "ready": True},
        evidence_fingerprint="fp-1",
    )
    assert result["ok"] is True
    assert result["learning_status"] == "review_candidate"


@pytest.mark.asyncio
async def test_record_learning_candidate_low_rating_stays_recorded():
    db = _FakeDb()
    result = await record_learning_candidate(
        db,
        organization_id="org-1",
        user_id="user-1",
        artifact_id="artifact-1",
        artifact_version_id="version-1",
        change_type="edited",
        rating=2,
        comment="不行",
        original_content="旧内容",
        revised_content="新内容",
        quality_before={"score": 80, "ready": False},
        quality_after={"score": 85, "ready": True},
        evidence_fingerprint="fp-1",
    )
    assert result["learning_status"] == "recorded"


@pytest.mark.asyncio
async def test_summarize_failure_modes_ranks_codes():
    db = _FakeDb()
    db.records = [
        {
            "artifact_type": "customer_solution",
            "score": 80,
            "ready": False,
            "findings": [
                {"code": "evidence_insufficient"},
                {"code": "section_depth_insufficient"},
            ],
        },
        {
            "artifact_type": "tender",
            "score": 90,
            "ready": True,
            "findings": [{"code": "evidence_insufficient"}],
        },
    ]
    result = await summarize_failure_modes(db, organization_id="org-1", days=30)
    assert result["available"] is True
    assert result["sample_size"] == 2
    assert result["failure_modes"][0]["code"] == "evidence_insufficient"
    assert result["failure_modes"][0]["count"] == 2


@pytest.mark.asyncio
async def test_record_customer_outcome_rejects_unknown():
    db = _FakeDb()
    result = await record_customer_outcome(
        db,
        organization_id="org-1",
        user_id="user-1",
        artifact_id="artifact-1",
        artifact_version_id="version-1",
        outcome="unknown",
    )
    assert result["ok"] is False


@pytest.mark.asyncio
async def test_record_customer_outcome_persists_won():
    db = _FakeDb()
    result = await record_customer_outcome(
        db,
        organization_id="org-1",
        user_id="user-1",
        artifact_id="artifact-1",
        artifact_version_id="version-1",
        outcome="won",
        rating=5,
    )
    assert result["ok"] is True
    assert db.records[0]["outcome"] == "won"
