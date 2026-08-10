import pytest

from app.services.artifact_template_service import (
    build_template_system_prompt,
    get_optimal_template,
    record_template_usage,
    save_template,
)


class _FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = {}
        self.single = False

    def select(self, *cols):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self

    async def execute(self):
        rows = [
            row
            for row in self.rows
            if all(row.get(k) == v for k, v in self.filters.items())
        ]
        if self.single:
            return _Result(rows[0] if rows else None)
        return _Result(rows)

    def maybe_single(self):
        self.single = True
        return self

    def insert(self, payload):
        self.rows = [payload]
        return self

    def update(self, payload):
        self.rows = [payload]
        return self


class _FakeDb:
    def __init__(self, rows=None):
        self.rows = rows or []

    def table(self, name):
        return _FakeQuery(self.rows)


class _Result:
    def __init__(self, data):
        self.data = data


@pytest.mark.asyncio
async def test_get_optimal_template_picks_best_metrics():
    db = _FakeDb(
        [
            {
                "organization_id": "org-1",
                "template_key": "t-plain",
                "artifact_type": "customer_solution",
                "status": "active",
                "metrics": {"usage_count": 1, "avg_score": 70, "ready_rate": 0.5},
            },
            {
                "organization_id": "org-1",
                "template_key": "t-gold",
                "artifact_type": "customer_solution",
                "status": "active",
                "metrics": {"usage_count": 10, "avg_score": 92, "ready_rate": 0.95},
            },
        ]
    )
    template = await get_optimal_template(
        db, organization_id="org-1", artifact_type="customer_solution"
    )
    assert template is not None
    assert template["template_key"] == "t-gold"


@pytest.mark.asyncio
async def test_get_optimal_template_returns_none_when_empty():
    db = _FakeDb()
    template = await get_optimal_template(
        db, organization_id="org-1", artifact_type="tender"
    )
    assert template is None


@pytest.mark.asyncio
async def test_save_template_persists_payload():
    db = _FakeDb()
    result = await save_template(
        db,
        organization_id="org-1",
        user_id="user-1",
        template_key="pharma.solution",
        artifact_type="customer_solution",
        title="药企 QC 解决方案",
        sections=["背景", "方案", "验收"],
        instrument_line="chromatography",
        industry="pharmaceutical",
    )
    assert result["ok"] is True
    assert result["template"]["template_key"] == "pharma.solution"


@pytest.mark.asyncio
async def test_record_template_usage_folds_metrics():
    db = _FakeDb(
        [
            {
                "organization_id": "org-1",
                "template_key": "t-1",
                "status": "active",
                "metrics": {
                    "usage_count": 1,
                    "avg_score": 80,
                    "ready_rate": 0.5,
                    "ready_total": 0,
                },
            }
        ]
    )
    result = await record_template_usage(
        db,
        organization_id="org-1",
        template_key="t-1",
        quality={"score": 92, "ready": True},
    )
    assert result["ok"] is True
    metrics = result["metrics"]
    assert metrics["usage_count"] == 2
    assert metrics["avg_score"] == 86.0
    assert metrics["ready_rate"] == 0.5


def test_build_template_system_prompt_includes_skeleton():
    prompt = build_template_system_prompt(
        {
            "title": "模板",
            "sections": ["背景", "方案"],
            "content_markdown": "框架内容",
        },
        None,
    )
    assert "黄金模板参考" in prompt
    assert "背景 → 方案" in prompt


def test_build_template_system_prompt_empty_for_none():
    assert build_template_system_prompt(None, None) == ""
