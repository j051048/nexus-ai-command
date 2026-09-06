from types import SimpleNamespace

import pytest

from app.services.agent_slo_cost_service import summarize_agent_slo_cost
from app.services.bounded_query_service import collect_bounded_rows


@pytest.mark.parametrize("size,cap,complete", [(1201, 2000, True), (2000, 2000, True), (2001, 2000, False)])
@pytest.mark.asyncio
async def test_pagination_reports_truncation(size, cap, complete):
    class Query:
        def range(self, start, end):
            self.bounds = start, end
            return self

        async def execute(self):
            start, end = self.bounds
            return SimpleNamespace(data=[{"id": i} for i in range(start, min(end + 1, size))])

    rows, actual = await collect_bounded_rows(Query, cap=cap)
    assert len(rows) == min(size, cap)
    assert actual is complete


def test_no_data_or_failed_query_cannot_prove_healthy():
    assert summarize_agent_slo_cost()["status"] == "insufficient_data"
    assert summarize_agent_slo_cost()["metrics"]["agent_success_rate"] is None
    assert summarize_agent_slo_cost(unavailable_sources=["llm_call_log"])["status"] == "unavailable"


def test_weekly_window_cost_is_not_compared_to_single_day_budget():
    result = summarize_agent_slo_cost(
        llm_calls=[{"call_cost": 70, "agent_code": "writer"}], window_days=7,
    )
    assert result["metrics"]["average_daily_cost_usd"] == 10
    assert "daily_cost_above_budget" not in result["violations"]
    assert result["agent_costs"] == [{"agent_code": "writer", "calls": 1, "cost_usd": 70}]
