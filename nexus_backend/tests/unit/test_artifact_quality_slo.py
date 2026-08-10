import pytest

from app.services.artifact_quality_slo import (
    SLO_CONFIG,
    build_monthly_report,
    evaluate_slo,
)


class _FakeDb:
    def __init__(self, rows):
        self.rows = rows

    def table(self, name):
        return _FakeQuery(self.rows)


class _FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.conditions = []

    def select(self, *cols):
        return self

    def eq(self, key, value):
        self.conditions.append((key, value))
        return self

    def gte(self, key, value):
        self.conditions.append((key, value))
        return self

    def lt(self, key, value):
        self.conditions.append((key, value))
        return self

    def limit(self, n):
        return self

    async def execute(self):
        return _Result(self.rows)


class _Result:
    def __init__(self, data):
        self.data = data


def _event(
    score, ready, coverage=95.0, artifact_type="customer_solution", template=None
):
    return {
        "artifact_type": artifact_type,
        "score": score,
        "ready": ready,
        "repair_count": 0 if ready else 2,
        "dimensions": {"evidence_coverage": coverage},
        "template_key": template,
        "findings": (
            [{"code": "evidence_insufficient"}] if not ready else [{"code": "ok"}]
        ),
    }


@pytest.mark.asyncio
async def test_evaluate_slo_reports_targets():
    db = _FakeDb(
        [
            _event(92, True),
            _event(88, True),
            _event(60, False, coverage=70.0),
        ]
    )
    result = await evaluate_slo(db, organization_id="org-1", days=30)
    assert result["available"] is True
    assert result["slo"]["ready_rate"]["target"] == SLO_CONFIG["ready_rate"]["target"]
    assert result["slo"]["avg_score"]["target"] == SLO_CONFIG["avg_score"]["target"]
    assert (
        result["slo"]["evidence_coverage"]["target"]
        == SLO_CONFIG["evidence_coverage"]["target"]
    )
    # ready 2/3 < 0.9 -> warn
    assert result["overall"] == "warn"


@pytest.mark.asyncio
async def test_evaluate_slo_all_ok():
    db = _FakeDb([_event(92, True), _event(88, True), _event(90, True)])
    result = await evaluate_slo(db, organization_id="org-1", days=30)
    assert result["overall"] == "ok"


@pytest.mark.asyncio
async def test_evaluate_slo_empty_returns_unavailable():
    db = _FakeDb([])
    result = await evaluate_slo(db, organization_id="org-1", days=30)
    assert result["available"] is False


@pytest.mark.asyncio
async def test_build_monthly_report_groups_by_type_and_template():
    db = _FakeDb(
        [
            _event(92, True, template="pharma"),
            _event(80, False, coverage=88.0, artifact_type="tender"),
            _event(95, True, template="pharma"),
        ]
    )
    report = await build_monthly_report(db, organization_id="org-1", year=2026, month=8)
    assert report["available"] is True
    assert report["period"] == "2026-08"
    assert report["report"]["by_artifact_type"]["customer_solution"] == 2
    assert report["report"]["by_template"]["pharma"] == 2
    assert any(
        item["code"] == "evidence_insufficient"
        for item in report["report"]["failure_modes"]
    )


@pytest.mark.asyncio
async def test_build_monthly_report_invalid_month():
    db = _FakeDb([])
    report = await build_monthly_report(
        db, organization_id="org-1", year=2026, month=13
    )
    assert report["available"] is False
