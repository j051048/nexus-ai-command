"""Lead Scoring Service 单元测试"""

from datetime import datetime, timezone, timedelta

import pytest

from app.services.lead_scoring_service import (
    score_lead,
    _recency_score,
    _engagement_score,
    _completeness_score,
    STAGE_WEIGHTS,
    STAGE_WIN_PROBABILITY,
)


class TestRecencyScore:
    def test_updated_today(self):
        lead = {"updated_at": datetime.now(timezone.utc).isoformat()}
        assert _recency_score(lead) == 100

    def test_updated_10_days_ago(self):
        dt = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        lead = {"updated_at": dt}
        score = _recency_score(lead)
        assert 10 < score < 100  # Should be between min and max

    def test_updated_30_plus_days_ago(self):
        dt = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()
        lead = {"updated_at": dt}
        assert _recency_score(lead) == 10

    def test_no_updated_at(self):
        lead = {}
        assert _recency_score(lead) == 0

    def test_string_timestamp(self):
        dt = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        lead = {"updated_at": dt}
        assert _recency_score(lead) > 10


class TestEngagementScore:
    def test_all_fields_present(self):
        lead = {
            "contact_person": "张三",
            "phone": "13800138000",
            "email": "test@example.com",
            "notes": "这是一段超过10个字的备注信息",
        }
        assert _engagement_score(lead) == 100

    def test_no_fields(self):
        lead = {}
        assert _engagement_score(lead) == 0

    def test_partial_fields(self):
        lead = {"contact_person": "张三", "phone": "13800138000"}
        assert _engagement_score(lead) == 50

    def test_short_notes(self):
        lead = {"notes": "短"}
        assert _engagement_score(lead) == 0


class TestCompletenessScore:
    def test_all_fields_filled(self):
        lead = {
            "customer_name": "ABC",
            "contact_person": "张三",
            "phone": "138",
            "email": "a@b",
            "source": "web",
            "notes": "some",
        }
        assert _completeness_score(lead) == 100.0

    def test_no_fields(self):
        lead = {}
        assert _completeness_score(lead) == 0.0

    def test_half_fields(self):
        lead = {"customer_name": "ABC", "contact_person": "张三", "phone": "138"}
        score = _completeness_score(lead)
        assert 0 < score < 100


class TestScoreLead:
    def test_initial_stage(self):
        lead = {"stage": "initial", "updated_at": datetime.now(timezone.utc).isoformat()}
        result = score_lead(lead)
        assert "score" in result
        assert "win_probability" in result
        assert "ai_suggestion" in result
        assert "last_scored_at" in result
        assert 0 <= result["score"] <= 100
        assert 0 <= result["win_probability"] <= 1.0

    def test_won_stage(self):
        lead = {"stage": "won", "updated_at": datetime.now(timezone.utc).isoformat()}
        result = score_lead(lead)
        # win_probability = 1.0 * 0.7 + score_factor * 0.3, capped at 1.0
        assert result["win_probability"] >= 0.7
        assert result["score"] > 50

    def test_lost_stage(self):
        lead = {"stage": "lost"}
        result = score_lead(lead)
        assert result["win_probability"] == 0.0

    def test_default_stage(self):
        lead = {"stage": "unknown_stage"}
        result = score_lead(lead)
        assert "score" in result
        assert result["score"] > 0

    def test_full_lead(self):
        lead = {
            "stage": "negotiation",
            "customer_name": "ABC公司",
            "contact_person": "张三",
            "phone": "13800138000",
            "email": "test@abc.com",
            "source": "referral",
            "notes": "非常有意向的客户，已经进入价格谈判阶段",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        result = score_lead(lead)
        assert result["score"] > 60
        assert result["win_probability"] > 0.5

    def test_all_stages_have_weights(self):
        for stage in ["initial", "contacted", "qualified", "proposal", "negotiation", "won", "lost"]:
            assert stage in STAGE_WEIGHTS
            assert stage in STAGE_WIN_PROBABILITY
