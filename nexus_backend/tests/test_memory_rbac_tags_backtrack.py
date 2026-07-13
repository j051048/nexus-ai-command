"""Tests for P1.1 Visibility, P2.1 Semantic Tags, P2.2 Backtrack Strategy.

These tests validate the core logic of the three new memory system modules
without requiring database connections or LLM calls.
"""

import pytest

# ── P1.1: Visibility & RBAC Tests ──────────────────────────────────────────


class TestVisibility:
    """Test memory visibility and RBAC access control."""

    def test_private_visibility_owner_access(self):
        from app.services.conversation_memory.visibility import can_access_memory

        assert can_access_memory(
            memory_visibility="private",
            memory_user_id="user-1",
            memory_org_id="org-1",
            requesting_user_id="user-1",
            requesting_org_id="org-1",
            requesting_role="employee",
        )

    def test_private_visibility_blocks_other_user(self):
        from app.services.conversation_memory.visibility import can_access_memory

        assert not can_access_memory(
            memory_visibility="private",
            memory_user_id="user-1",
            memory_org_id="org-1",
            requesting_user_id="user-2",
            requesting_org_id="org-1",
            requesting_role="employee",
        )

    def test_team_visibility_allows_same_org(self):
        from app.services.conversation_memory.visibility import can_access_memory

        assert can_access_memory(
            memory_visibility="team",
            memory_user_id="user-1",
            memory_org_id="org-1",
            requesting_user_id="user-2",
            requesting_org_id="org-1",
            requesting_role="employee",
        )

    def test_team_visibility_blocks_cross_org(self):
        from app.services.conversation_memory.visibility import can_access_memory

        assert not can_access_memory(
            memory_visibility="team",
            memory_user_id="user-1",
            memory_org_id="org-1",
            requesting_user_id="user-3",
            requesting_org_id="org-2",
            requesting_role="admin",
        )

    def test_org_visibility_requires_manager(self):
        from app.services.conversation_memory.visibility import can_access_memory

        # Employee cannot see org-level memories
        assert not can_access_memory(
            memory_visibility="organization",
            memory_user_id="user-1",
            memory_org_id="org-1",
            requesting_user_id="user-2",
            requesting_org_id="org-1",
            requesting_role="employee",
        )
        # Manager can see org-level memories
        assert can_access_memory(
            memory_visibility="organization",
            memory_user_id="user-1",
            memory_org_id="org-1",
            requesting_user_id="user-2",
            requesting_org_id="org-1",
            requesting_role="manager",
        )

    def test_determine_visibility_default_private(self):
        from app.services.conversation_memory.visibility import determine_visibility

        assert determine_visibility("preference", 0.5) == "private"

    def test_policy_requires_explicit_org_visibility(self):
        from app.services.conversation_memory.visibility import determine_visibility

        assert determine_visibility("policy", 0.9) == "private"

    def test_importance_does_not_grant_team_visibility(self):
        from app.services.conversation_memory.visibility import determine_visibility

        assert determine_visibility("fact", 0.85) == "private"

    def test_determine_visibility_explicit_override(self):
        from app.services.conversation_memory.visibility import determine_visibility

        assert determine_visibility("preference", 0.3, explicit_visibility="team") == "team"

    def test_role_hierarchy(self):
        from app.services.conversation_memory.visibility import get_role_level

        assert get_role_level("employee") < get_role_level("team_lead")
        assert get_role_level("team_lead") < get_role_level("manager")
        assert get_role_level("manager") < get_role_level("admin")
        assert get_role_level("admin") < get_role_level("super_admin")


# ── P2.1: Semantic Tags Tests ─────────────────────────────────────────────


class TestSemanticTags:
    """Test semantic tag generation and overlap computation."""

    def test_domain_tag_extraction_crm(self):
        from app.services.conversation_memory.semantic_tags import generate_semantic_tags

        tags = generate_semantic_tags("fact", "customer_info", "华东区客户跟进效果不错")
        assert "crm" in tags

    def test_domain_tag_extraction_hr(self):
        from app.services.conversation_memory.semantic_tags import generate_semantic_tags

        tags = generate_semantic_tags("fact", "leave", "员工请假需要提前三天审批")
        assert "hr" in tags

    def test_domain_tag_extraction_finance(self):
        from app.services.conversation_memory.semantic_tags import generate_semantic_tags

        tags = generate_semantic_tags("fact", "budget", "Q3预算报销总额为50万")
        assert "finance" in tags

    def test_action_tag_from_category(self):
        from app.services.conversation_memory.semantic_tags import generate_semantic_tags

        tags = generate_semantic_tags("preference", "style", "我喜欢简洁的报告格式")
        assert "preference" in tags

    def test_person_entity_tag(self):
        from app.services.conversation_memory.semantic_tags import generate_semantic_tags

        tags = generate_semantic_tags("fact", "key_person", "张总负责华东区大客户")
        assert any(t.startswith("person:") for t in tags)

    def test_company_entity_tag(self):
        from app.services.conversation_memory.semantic_tags import generate_semantic_tags

        tags = generate_semantic_tags("fact", "partner", "华为公司是我们的核心合作伙伴")
        assert any(t.startswith("company:") for t in tags)

    def test_high_priority_tag(self):
        from app.services.conversation_memory.semantic_tags import generate_semantic_tags

        tags = generate_semantic_tags("explicit_memory", "rule", "记住永远不要删除客户数据")
        assert "high_priority" in tags

    def test_max_8_tags(self):
        from app.services.conversation_memory.semantic_tags import generate_semantic_tags

        # Input with many potential tags
        tags = generate_semantic_tags(
            "explicit_memory",
            "complex",
            "张总经理在华东公司负责客户审批报销系统项目管理，记住必须每天审核员工请假",
        )
        assert len(tags) <= 8

    def test_tag_overlap_computation(self):
        from app.services.conversation_memory.semantic_tags import compute_tag_overlap

        assert compute_tag_overlap(["crm", "person:张总"], ["crm", "fact"]) == 0.5
        assert compute_tag_overlap(["crm"], ["crm"]) == 1.0
        assert compute_tag_overlap(["hr"], ["crm"]) == 0.0
        assert compute_tag_overlap([], ["crm"]) == 0.0

    def test_query_tag_extraction(self):
        from app.services.conversation_memory.semantic_tags import extract_query_tags

        tags = extract_query_tags("张总的客户跟进情况怎么样")
        assert "crm" in tags
        assert any(t.startswith("person:") for t in tags)

    def test_fact_type_tag(self):
        from app.services.conversation_memory.semantic_tags import generate_semantic_tags

        tags = generate_semantic_tags("fact", "opinion", "这个方案不太好", fact_type="opinion")
        assert "type:opinion" in tags


# ── P2.2: Backtrack Strategy Tests ─────────────────────────────────────────


class TestBacktrackStrategy:
    """Test ToT-inspired backtracking logic."""

    def test_should_backtrack_no_candidates(self):
        from app.agent.backtrack_strategy import should_backtrack

        state = {
            "confidence_score": 0.2,
            "candidate_plans": [],
            "backtrack_depth": 0,
            "completed_tool_calls": [],
        }
        assert not should_backtrack(state)

    def test_should_backtrack_high_confidence(self):
        from app.agent.backtrack_strategy import should_backtrack

        state = {
            "confidence_score": 0.9,
            "candidate_plans": [{"sig": "abc", "score": 0.8}],
            "backtrack_depth": 0,
            "completed_tool_calls": [],
        }
        assert not should_backtrack(state)

    def test_should_backtrack_low_confidence_with_candidates(self):
        from app.agent.backtrack_strategy import should_backtrack

        state = {
            "confidence_score": 0.2,
            "candidate_plans": [{"sig": "alt1", "score": 0.7}],
            "backtrack_depth": 0,
            "completed_tool_calls": [],
            "plan": "current plan",
        }
        assert should_backtrack(state)

    def test_should_backtrack_max_depth_reached(self):
        from app.agent.backtrack_strategy import should_backtrack

        state = {
            "confidence_score": 0.1,
            "candidate_plans": [{"sig": "alt", "score": 0.8}],
            "backtrack_depth": 1,  # already at max
            "completed_tool_calls": [],
        }
        assert not should_backtrack(state)

    def test_should_backtrack_all_tools_failed(self):
        from app.agent.backtrack_strategy import should_backtrack

        state = {
            "confidence_score": 0.5,  # Not low enough on its own
            "candidate_plans": [{"sig": "alt", "score": 0.6}],
            "backtrack_depth": 0,
            "plan": "current",
            "completed_tool_calls": [
                {"tool_name": "search", "status": "error"},
                {"tool_name": "query", "status": "error"},
            ],
        }
        assert should_backtrack(state)

    def test_execute_backtrack_returns_updates(self):
        from app.agent.backtrack_strategy import execute_backtrack

        state = {
            "confidence_score": 0.2,
            "candidate_plans": [
                {"sig": "alt1", "score": 0.8, "msg_snapshot": None},
                {"sig": "alt2", "score": 0.5, "msg_snapshot": None},
            ],
            "backtrack_depth": 0,
            "plan": "failed plan",
        }
        updates = execute_backtrack(state)
        assert updates["backtrack_depth"] == 1
        assert updates["needs_replanning"] is True
        assert "reflection_guidance" in updates
        assert "寻路回溯" in updates["reflection_guidance"]

    def test_plan_signature_consistency(self):
        from app.agent.backtrack_strategy import _plan_signature

        sig1 = _plan_signature("查询客户信息并生成报告")
        sig2 = _plan_signature("查询客户信息并生成报告")
        sig3 = _plan_signature("完全不同的方案")
        assert sig1 == sig2
        assert sig1 != sig3

    def test_record_plan_candidate(self):
        from app.agent.backtrack_strategy import record_plan_candidate

        candidate = record_plan_candidate("测试方案", 0.75)
        assert candidate["score"] == 0.75
        assert "sig" in candidate
        assert len(candidate["sig"]) == 12


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
