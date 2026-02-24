"""Tests for event_bus: subscribe, publish, Event serialization."""

import pytest

from app.services.event_bus import Event, EventType, InMemoryEventBus


class TestEvent:
    def test_event_creation(self):
        event = Event(type=EventType.DOCUMENT_UPLOADED, payload={"doc_id": "1"})
        assert event.type == EventType.DOCUMENT_UPLOADED
        assert event.payload["doc_id"] == "1"
        assert event.id is not None
        assert event.timestamp is not None

    def test_event_to_dict(self):
        event = Event(
            type=EventType.BADGE_AWARDED,
            payload={"badge": "gold"},
            user_id="user-1",
        )
        d = event.to_dict()
        assert d["type"] == EventType.BADGE_AWARDED
        assert d["payload"]["badge"] == "gold"
        assert d["user_id"] == "user-1"

    def test_event_from_dict(self):
        event = Event(
            type=EventType.APPROVAL_SUBMITTED,
            payload={"approval_id": "a1"},
            user_id="user-1",
        )
        d = event.to_dict()
        restored = Event.from_dict(d)
        assert restored.type == event.type
        assert restored.payload == event.payload
        assert restored.user_id == event.user_id


class TestEventBus:
    @pytest.mark.asyncio
    async def test_subscribe_and_publish_sync(self):
        bus = InMemoryEventBus()
        received = []

        async def handler(event: Event):
            received.append(event)

        bus.subscribe(EventType.DOCUMENT_UPLOADED, handler)
        event = Event(type=EventType.DOCUMENT_UPLOADED, payload={"doc": "test"})
        await bus.publish_sync(event)
        assert len(received) == 1
        assert received[0].payload["doc"] == "test"

    @pytest.mark.asyncio
    async def test_wildcard_handler(self):
        bus = InMemoryEventBus()
        received = []

        async def handler(event: Event):
            received.append(event)

        bus.subscribe("*", handler)
        event = Event(type=EventType.APPROVAL_SUBMITTED, payload={})
        await bus.publish_sync(event)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        bus = InMemoryEventBus()
        received = []

        async def handler(event: Event):
            received.append(event)

        bus.subscribe(EventType.DOCUMENT_UPLOADED, handler)
        bus.unsubscribe(EventType.DOCUMENT_UPLOADED, handler)
        event = Event(type=EventType.DOCUMENT_UPLOADED, payload={})
        await bus.publish_sync(event)
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_multiple_handlers(self):
        bus = InMemoryEventBus()
        results = {"h1": 0, "h2": 0}

        async def handler1(event: Event):
            results["h1"] += 1

        async def handler2(event: Event):
            results["h2"] += 1

        bus.subscribe(EventType.DEAL_WON, handler1)
        bus.subscribe(EventType.DEAL_WON, handler2)
        event = Event(type=EventType.DEAL_WON, payload={})
        await bus.publish_sync(event)
        assert results["h1"] == 1
        assert results["h2"] == 1

    @pytest.mark.asyncio
    async def test_event_history(self):
        bus = InMemoryEventBus()
        event = Event(type=EventType.BADGE_AWARDED, payload={"badge": "star"})
        # publish (async) adds to history; publish_sync does not
        await bus.publish(event)
        assert len(bus._event_history) >= 1
