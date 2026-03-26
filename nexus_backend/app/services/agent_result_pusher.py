"""
Unified agent result push: notification + WebSocket + chat persistence.

Extracted from scheduled_task_runner and auto_trigger_service to eliminate
duplicated three-step push logic.
"""

import logging

logger = logging.getLogger(__name__)


async def push_agent_result(
    user_id: str,
    title: str,
    message: str,
    *,
    agent_name: str = "proactive_agent",
    metadata: dict | None = None,
    org_id: str | None = None,
    session_id: str = "default",
) -> None:
    """Push an agent result via notification, WebSocket, and chat persistence."""
    # 1. Send notification
    try:
        from app.services.notification_service import send_notification

        await send_notification(
            title=title,
            content=message[:500],
            target_user_id=user_id,
        )
    except Exception as e:
        logger.error("[push_agent_result] Notification failed: %s", e)

    # 2. Push to chat via WebSocket
    try:
        from app.services.websocket_manager import ws_manager

        if ws_manager.is_connected(user_id):
            await ws_manager.send_to_user(user_id, {
                "type": "proactive_chat",
                "data": {
                    "session_id": session_id,
                    "title": title,
                    "message": message,
                    **(metadata or {}),
                },
            })
    except Exception as e:
        logger.error("[push_agent_result] WS push failed: %s", e)

    # 3. Save as chat message for persistence
    try:
        from app.services.chat_service import ChatService

        await ChatService.save_message(
            user_id=user_id,
            session_id=session_id,
            role="assistant",
            content=message,
            agent=agent_name,
            metadata={"source": "proactive", **(metadata or {})},
            org_id=org_id,
        )
    except Exception as e:
        logger.error("[push_agent_result] Chat save failed: %s", e)
