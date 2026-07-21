import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage

from app.agent.middlewares import memory_inject_middleware
from app.agent.skill_library import SkillLibrary, skill_library
from app.agent.state import AgentConfig


class RecordingQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []

    def select(self, *args, **kwargs):
        del args, kwargs
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def order(self, *args, **kwargs):
        del args, kwargs
        return self

    def limit(self, value):
        del value
        return self

    async def execute(self):
        return SimpleNamespace(data=self.rows)


class RecordingDb:
    def __init__(self, rows):
        self.query = RecordingQuery(rows)

    def table(self, name):
        assert name == "conversation_memories"
        return self.query


@pytest.mark.asyncio
async def test_keyword_skill_fallback_always_filters_organization():
    db = RecordingDb(
        [
            {
                "key": "skill:1",
                "value": json.dumps(
                    {
                        "intent_pattern": "生成 客户 方案",
                        "tool_chain": [{"tool": "solution", "param_keys": []}],
                    },
                    ensure_ascii=False,
                ),
                "metadata": {"intent_pattern": "生成 客户 方案"},
                "importance": 0.8,
            }
        ]
    )

    matched = await SkillLibrary()._match_skill_keyword(
        "生成 客户 方案",
        "user-1",
        "org-1",
        db,
    )

    assert matched is not None
    assert ("user_id", "user-1") in db.query.filters
    assert ("organization_id", "org-1") in db.query.filters


@pytest.mark.asyncio
async def test_prehydrated_memory_does_not_skip_skill_matching(monkeypatch):
    calls = []

    async def fake_match(*, user_message, user_id, org_id, db):
        del db
        calls.append((user_message, user_id, org_id))
        return {
            "intent_pattern": "生成方案",
            "tool_chain": [{"tool": "solution", "param_keys": []}],
        }

    monkeypatch.setattr(skill_library, "match_skill", fake_match)
    state = {
        "config": AgentConfig(user_id="user-1", org_id="org-1"),
        "messages": [HumanMessage(content="请生成客户方案")],
        "_memory_injected": True,
        "_skill_injected": False,
    }

    updates = await memory_inject_middleware(state)

    assert calls == [("请生成客户方案", "user-1", "org-1")]
    assert updates["_skill_injected"] is True
    assert updates["_matched_skill"]["intent_pattern"] == "生成方案"
    assert "建议工具链" in updates["_injected_memories"][0]
