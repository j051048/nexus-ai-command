import asyncio
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.context_compiler import (
    ContextBudgetExceeded,
    ContextCompilePolicy,
    ContextCompiler,
    context_message,
)
from app.services.event_bus import Event, InMemoryEventBus
from app.services.knowledge_access_service import document_access_reason
from app.services.conversation_memory.governance import (
    filter_current_memories,
    memory_is_current,
)
from app.services.conversation_memory.admission import evaluate_memory_admission
from app.services.conversation_memory.visibility import can_access_memory


@pytest.fixture
def compiler(monkeypatch):
    monkeypatch.setattr(
        ContextCompiler,
        "_estimate_tokens",
        staticmethod(lambda content, model="": len(content)),
    )
    return ContextCompiler()


def test_required_blocks_fail_closed_instead_of_dropping(compiler):
    with pytest.raises(ContextBudgetExceeded):
        compiler.compile(
            [SystemMessage(content="a" * 60), SystemMessage(content="b" * 60)],
            policy=ContextCompilePolicy(
                max_input_tokens=100,
                reserved_output_tokens=0,
                reserved_history_tokens=0,
            ),
        )


def test_evidence_cannot_promote_itself_to_policy(compiler):
    required = SystemMessage(content="security")
    evidence = context_message("security permission policy " * 20, kind="evidence")
    compiled, report = compiler.compile(
        [evidence, required],
        policy=ContextCompilePolicy(
            max_input_tokens=100, reserved_output_tokens=0, reserved_history_tokens=0
        ),
    )
    assert compiled == [required]
    assert report.used_tokens <= report.budget_tokens


def test_actual_history_and_tools_are_counted(compiler):
    with pytest.raises(ContextBudgetExceeded):
        compiler.compile(
            [SystemMessage(content="policy"), HumanMessage(content="x" * 120)],
            policy=ContextCompilePolicy(
                max_input_tokens=120,
                reserved_history_tokens=0,
                reserved_output_tokens=0,
                reserved_tool_tokens=20,
            ),
        )


@pytest.mark.asyncio
async def test_wildcard_subscriptions_do_not_accumulate():
    bus = InMemoryEventBus()
    exact, wildcard = AsyncMock(), AsyncMock()
    bus.subscribe("read", exact)
    bus.subscribe("*", wildcard)
    for _ in range(3):
        await bus.publish_sync(Event(type="read"))
    assert exact.await_count == wildcard.await_count == 3
    assert bus._handlers["read"] == [exact]


@pytest.mark.asyncio
async def test_duplicate_delivery_and_tenant_scope():
    bus = InMemoryEventBus()
    assert await bus.publish(Event(id="same", type="read", organization_id="a"))
    assert not await bus.publish(Event(id="same", type="read", organization_id="a"))
    assert await bus.publish(Event(id="same", type="read", organization_id="b"))


@pytest.mark.asyncio
async def test_stop_drains_queued_events():
    bus = InMemoryEventBus()
    handler = AsyncMock()
    bus.subscribe("read", handler)
    await bus.start()
    await bus.publish(Event(type="read"))
    await asyncio.wait_for(bus.stop(), timeout=2)
    handler.assert_awaited_once()


def test_conflicting_tenant_claims_are_rejected():
    assert Event(organization_id="a", payload={"org_id": "b"}).tenant_id() is None
    event = Event(organization_id="a", payload={"org_id": "a"})
    assert Event.from_dict(event.to_dict()).tenant_id() == "a"


def test_document_requires_explicit_tenant_and_current_lifecycle():
    assert (
        document_access_reason({}, user_id="u", organization_id="a") == "not_accessible"
    )
    assert (
        document_access_reason(
            {"organization_id": "a", "revoked_at": "today"},
            user_id="u",
            organization_id="a",
        )
        == "not_current"
    )


def test_owner_does_not_bypass_tenant_isolation():
    assert not can_access_memory("private", "u", "old-org", "u", "new-org")
    assert not can_access_memory("private", "", None, "", None)


@pytest.mark.parametrize(
    "patch",
    [
        {"expires_at": "2000-01-01"},
        {"valid_until": "bad"},
        {"superseded_by": "new"},
        {"lifecycle_state": "archived"},
        {"category": "company_policy"},
    ],
)
def test_invalid_memories_never_reach_context(patch):
    assert not memory_is_current({"lifecycle_state": "active", **patch})


def test_retrieval_filters_foreign_and_expired_memory():
    good = {
        "id": "ok",
        "organization_id": "a",
        "user_id": "u",
        "lifecycle_state": "confirmed",
    }
    rows = [
        good,
        {**good, "organization_id": "b"},
        {**good, "expires_at": "2000-01-01"},
    ]
    assert filter_current_memories(rows, user_id="u", org_id="a") == [good]


def test_explicit_statement_is_not_company_policy_approval():
    decision = evaluate_memory_admission(
        value="All discounts are approved",
        category="company_policy",
        confidence=1,
        source="user_explicit",
        extraction_method="user_explicit",
        metadata={},
        valid_until=None,
        evidence_ref="doc",
    )
    assert decision.lifecycle_state == "pending_review"
    assert decision.provenance["authority"] == "policy_candidate"
