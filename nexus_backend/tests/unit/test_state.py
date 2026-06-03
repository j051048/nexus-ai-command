"""
AgentState / AgentConfig / ThinkingStep / WBS 数据结构单元测试

覆盖：枚举值、Pydantic 校验、默认值、边界值、序列化
"""
import pytest
from pydantic import ValidationError

from app.agent.state import (
    AgentConfig,
    AgentPhase,
    QueryComplexity,
    ThinkingStep,
    ToolCallRecord,
    WBSStructure,
    WBSSubTask,
)


class TestAgentPhase:
    def test_all_phases_exist(self):
        phases = {p.value for p in AgentPhase}
        expected = {"routing", "planning", "executing", "reflecting", "critiquing", "responding", "done", "error"}
        assert phases == expected

    def test_str_enum(self):
        assert str(AgentPhase.ROUTING) == "routing"
        assert AgentPhase.DONE == "done"


class TestQueryComplexity:
    def test_model_tier_mapping(self):
        assert QueryComplexity.SIMPLE.model_tier == "economy"
        assert QueryComplexity.MODERATE.model_tier == "balanced"
        assert QueryComplexity.COMPLEX.model_tier == "power"
        assert QueryComplexity.CRITICAL.model_tier == "flagship"


class TestThinkingStep:
    def test_to_dict_excludes_none(self):
        step = ThinkingStep(phase="planning", content="分析意图")
        d = step.to_dict()
        assert "tool_name" not in d
        assert "tool_result" not in d
        assert d["phase"] == "planning"
        assert d["content"] == "分析意图"

    def test_to_dict_includes_tool_info(self):
        step = ThinkingStep(
            phase="executing",
            content="调用工具",
            tool_name="GetCustomersTool",
            tool_args={"limit": 10},
            tool_result="5 customers",
            duration_ms=230,
        )
        d = step.to_dict()
        assert d["tool_name"] == "GetCustomersTool"
        assert d["duration_ms"] == 230

    def test_timestamp_auto_set(self):
        step = ThinkingStep(phase="planning", content="test")
        assert step.timestamp > 0


class TestToolCallRecord:
    def test_defaults(self):
        tc = ToolCallRecord(
            tool_name="TestTool",
            tool_args={"a": 1},
            tool_call_id="tc-1",
        )
        assert tc.status == "pending"
        assert tc.confirmation_type == ""
        assert tc.error_type is None


class TestWBSStructure:
    def test_valid_structure(self):
        wbs = WBSStructure(
            title="营销方案",
            summary="Q2 营销计划",
            sub_tasks=[
                WBSSubTask(title="内容策划", agent_code="content_agent"),
                WBSSubTask(title="渠道投放", agent_code="media_agent", dependencies=[0]),
            ],
        )
        assert len(wbs.sub_tasks) == 2
        assert wbs.sub_tasks[1].dependencies == [0]

    def test_empty_sub_tasks(self):
        wbs = WBSStructure(title="空任务")
        assert wbs.sub_tasks == []


class TestAgentConfig:
    def test_defaults(self):
        config = AgentConfig(user_id="u-1")
        assert config.session_id == "default"
        assert config.model == "deepseek-v4-flash"
        assert config.mini_model == "deepseek-v4-flash"
        assert config.max_iterations == 5
        assert config.temperature == 0.5
        assert config.user_role == "employee"

    def test_invalid_max_iterations(self):
        with pytest.raises(ValidationError):
            AgentConfig(user_id="u-1", max_iterations=0)

    def test_invalid_temperature(self):
        with pytest.raises(ValidationError):
            AgentConfig(user_id="u-1", temperature=3.0)
        with pytest.raises(ValidationError):
            AgentConfig(user_id="u-1", temperature=-0.1)

    def test_invalid_user_role_defaults_to_employee(self):
        config = AgentConfig(user_id="u-1", user_role="")
        assert config.user_role == "employee"

    def test_get_model_for_complexity(self):
        config = AgentConfig(user_id="u-1", model="gpt-4o", mini_model="gpt-4o-mini")
        assert config.get_model_for_complexity(QueryComplexity.SIMPLE) == "deepseek-v4-flash"
        assert config.get_model_for_complexity(QueryComplexity.MODERATE) == "deepseek-v4-flash"

    def test_confidence_threshold_bounds(self):
        with pytest.raises(ValidationError):
            AgentConfig(user_id="u-1", confidence_threshold=1.5)

    def test_tool_timeout_positive(self):
        with pytest.raises(ValidationError):
            AgentConfig(user_id="u-1", tool_timeout=0)

    def test_dry_run_default_false(self):
        config = AgentConfig(user_id="u-1")
        assert config.dry_run is False
