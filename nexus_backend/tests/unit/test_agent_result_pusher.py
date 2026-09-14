from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.agent_result_pusher import push_agent_result
from app.services.chat_service import ChatService
from app.services import notification_service
from app.services.websocket_manager import ws_manager


@pytest.mark.asyncio
async def test_one_authoritative_event_identity_for_all_delivery_channels(monkeypatch):
    notification = AsyncMock()
    chat = AsyncMock()
    push = AsyncMock()
    monkeypatch.setattr(notification_service, "send_notification", notification)
    monkeypatch.setattr(ChatService, "save_message", chat)
    monkeypatch.setattr(ws_manager, "is_connected", MagicMock(return_value=True))
    monkeypatch.setattr(ws_manager, "send_to_user", push)
    await push_agent_result(
        "u",
        "title",
        "result",
        org_id="a",
        metadata={
            "organization_id": "b",
            "user_id": "other",
            "event_id": "spoof",
            "source": "wrong",
        },
    )
    payload = push.call_args.args[1]["data"]
    assert payload["organization_id"] == "a"
    assert payload["user_id"] == "u"
    assert payload["event_id"] != "spoof"
    assert chat.call_args.kwargs["metadata"]["event_id"] == payload["event_id"]
    assert chat.call_args.kwargs["metadata"]["source"] == "proactive"
    assert notification.call_args.kwargs["metadata"] == {
        "organization_id": "a",
        "event_id": payload["event_id"],
    }
