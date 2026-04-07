"""
Tests for cross-module event bus workflow handlers.
Validates the horizontal business flow:
Lead → Analysis → Approval → Contract → Payment
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.event_bus import (
    Event,
    EventType,
    InMemoryEventBus,
)


@pytest.fixture
def test_bus():
    """Create a fresh event bus for testing."""
    return InMemoryEventBus()


@pytest.fixture
def mock_supabase():
    """Mock the Supabase client."""
    mock = MagicMock()
    mock.table = MagicMock(return_value=mock)
    mock.insert = MagicMock(return_value=mock)
    mock.select = MagicMock(return_value=mock)
    mock.eq = MagicMock(return_value=mock)
    mock.in_ = MagicMock(return_value=mock)
    mock.execute = AsyncMock(return_value=MagicMock(data=[{"id": "admin-1"}]))
    mock.rpc = MagicMock(return_value=MagicMock(execute=AsyncMock()))
    return mock


class TestEventTypes:
    """Test that all cross-module event types are defined."""

    def test_sales_events_exist(self):
        assert EventType.LEAD_CREATED.value == "lead.created"
        assert EventType.LEAD_QUALIFIED.value == "lead.qualified"
        assert EventType.DEAL_WON.value == "deal.won"

    def test_contract_events_exist(self):
        assert EventType.CONTRACT_CREATED.value == "contract.created"
        assert EventType.CONTRACT_SIGNED.value == "contract.signed"
        assert EventType.CONTRACT_EXPIRING.value == "contract.expiring"

    def test_finance_events_exist(self):
        assert EventType.INVOICE_CREATED.value == "invoice.created"
        assert EventType.PAYMENT_RECEIVED.value == "payment.received"


class TestEventBusCore:
    """Test event bus subscription and dispatch."""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self, test_bus):
        received = []

        async def handler(event):
            received.append(event)

        test_bus.subscribe("test.event", handler)
        event = Event(type="test.event", payload={"key": "value"})
        await test_bus.publish_sync(event)

        assert len(received) == 1
        assert received[0].payload["key"] == "value"

    @pytest.mark.asyncio
    async def test_wildcard_handler(self, test_bus):
        received = []

        async def handler(event):
            received.append(event.type)

        test_bus.subscribe("*", handler)
        await test_bus.publish_sync(Event(type="a"))
        await test_bus.publish_sync(Event(type="b"))

        assert len(received) == 2

    @pytest.mark.asyncio
    async def test_unsubscribe(self, test_bus):
        received = []

        async def handler(event):
            received.append(event)

        test_bus.subscribe("test.event", handler)
        test_bus.unsubscribe("test.event", handler)
        await test_bus.publish_sync(Event(type="test.event"))

        assert len(received) == 0


class TestCrossModuleWorkflows:
    """Test the cross-module data workflow handlers."""

    @pytest.mark.asyncio
    async def test_deal_won_creates_contract(self, mock_supabase):
        """DEAL_WON should auto-create a contract draft."""
        from app.services.event_bus import auto_create_contract_from_deal

        event = Event(
            type=EventType.DEAL_WON.value,
            payload={
                "user_id": "user-1",
                "customer_name": "测试客户",
                "value": 50000,
                "deal_id": "deal-1",
                "org_id": "org-1",
            },
        )

        with patch("app.core.database.supabase", mock_supabase):
            await auto_create_contract_from_deal(event)

        # Should have called insert twice: once for contract, once for notification
        assert mock_supabase.table.call_count >= 2

    @pytest.mark.asyncio
    async def test_contract_signed_creates_invoice(self, mock_supabase):
        """CONTRACT_SIGNED should auto-create an invoice."""
        from app.services.event_bus import auto_create_invoice_from_contract

        event = Event(
            type=EventType.CONTRACT_SIGNED.value,
            payload={
                "contract_id": "contract-1",
                "amount": 100000,
                "customer_name": "大客户",
                "org_id": "org-1",
                "user_id": "user-1",
            },
        )

        with patch("app.core.database.supabase", mock_supabase):
            await auto_create_invoice_from_contract(event)

        assert mock_supabase.table.call_count >= 1

    @pytest.mark.asyncio
    async def test_lead_qualified_triggers_analysis(self, mock_supabase):
        """High-value LEAD_QUALIFIED should suggest tender analysis."""
        from app.services.event_bus import auto_trigger_tender_analysis

        event = Event(
            type=EventType.LEAD_QUALIFIED.value,
            payload={
                "user_id": "user-1",
                "estimated_value": 200000,
                "name": "大型项目",
            },
        )

        with patch("app.core.database.supabase", mock_supabase):
            await auto_trigger_tender_analysis(event)

        # Should create a notification
        mock_supabase.table.assert_called()

    @pytest.mark.asyncio
    async def test_lead_qualified_skips_low_value(self, mock_supabase):
        """Low-value leads should NOT trigger tender analysis."""
        from app.services.event_bus import auto_trigger_tender_analysis

        event = Event(
            type=EventType.LEAD_QUALIFIED.value,
            payload={
                "user_id": "user-1",
                "estimated_value": 5000,  # Below 100k threshold
                "name": "小项目",
            },
        )

        with patch("app.core.database.supabase", mock_supabase):
            await auto_trigger_tender_analysis(event)

        # Should NOT create any notifications
        mock_supabase.table.assert_not_called()

    @pytest.mark.asyncio
    async def test_payment_received_updates_metrics(self, mock_supabase):
        """PAYMENT_RECEIVED should update sales metrics and notify user."""
        from app.services.event_bus import update_sales_metrics_on_payment

        event = Event(
            type=EventType.PAYMENT_RECEIVED.value,
            payload={
                "user_id": "user-1",
                "amount": 100000,
                "org_id": "org-1",
            },
        )

        with patch("app.core.database.supabase", mock_supabase):
            await update_sales_metrics_on_payment(event)

        # Should call rpc for bonus and insert notification
        mock_supabase.rpc.assert_called()

    @pytest.mark.asyncio
    async def test_approval_triggers_contract_signed(self, mock_supabase):
        """Contract APPROVAL_APPROVED should emit CONTRACT_SIGNED."""
        from app.services.event_bus import trigger_downstream_on_approval

        event = Event(
            type=EventType.APPROVAL_APPROVED.value,
            payload={"type": "contract", "amount": 50000},
            user_id="user-1",
        )

        with patch("app.services.event_bus.emit", new_callable=AsyncMock) as mock_emit:
            await trigger_downstream_on_approval(event)
            mock_emit.assert_called_once()
            assert mock_emit.call_args[0][0] == EventType.CONTRACT_SIGNED.value


class TestEventHistory:
    """Test event history tracking."""

    @pytest.mark.asyncio
    async def test_event_stored_in_history(self, test_bus):
        event = Event(type="test", payload={"data": 1})
        await test_bus.publish(event)
        recent = test_bus.get_recent_events(limit=10)
        assert len(recent) == 1
        assert recent[0].id == event.id

    @pytest.mark.asyncio
    async def test_history_respects_max_limit(self, test_bus):
        test_bus._max_history = 5
        for i in range(10):
            await test_bus.publish(Event(type="test", payload={"i": i}))
        recent = test_bus.get_recent_events(limit=100)
        assert len(recent) == 5

    @pytest.mark.asyncio
    async def test_filter_history_by_type(self, test_bus):
        await test_bus.publish(Event(type="a"))
        await test_bus.publish(Event(type="b"))
        await test_bus.publish(Event(type="a"))
        recent = test_bus.get_recent_events(event_type="a")
        assert len(recent) == 2
