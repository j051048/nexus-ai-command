"""
WebSocket Connection Manager — enables server-push and bidirectional communication.

Manages WebSocket connections per user, supports:
- Server-initiated push (proactive notifications, trigger results)
- Real-time agent streaming via WebSocket (alternative to SSE)
- Connection lifecycle management with heartbeat
"""

import contextlib
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections keyed by user_id.

    Thread-safe for asyncio: all mutations happen in the event loop.
    Supports multiple connections per user (e.g., multiple browser tabs).
    """

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._heartbeat_interval = 30  # seconds

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)
        logger.info(f"[WS] User {user_id} connected (total: {len(self._connections[user_id])})")

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        """Remove a WebSocket connection."""
        if user_id in self._connections:
            self._connections[user_id] = [ws for ws in self._connections[user_id] if ws is not websocket]
            if not self._connections[user_id]:
                del self._connections[user_id]
            logger.info(f"[WS] User {user_id} disconnected")

    async def send_to_user(self, user_id: str, message: dict) -> int:
        """
        Send a JSON message to all connections of a specific user.

        Returns the number of connections that received the message.
        """
        connections = self._connections.get(user_id, [])
        if not connections:
            return 0

        sent = 0
        stale = []
        for ws in connections:
            try:
                await ws.send_json(message)
                sent += 1
            except Exception:
                stale.append(ws)

        # Clean up stale connections
        for ws in stale:
            self.disconnect(ws, user_id)

        return sent

    async def broadcast(self, message: dict, exclude_user: str | None = None) -> int:
        """Broadcast a message to all connected users."""
        sent = 0
        for user_id in list(self._connections.keys()):
            if user_id != exclude_user:
                sent += await self.send_to_user(user_id, message)
        return sent

    def is_connected(self, user_id: str) -> bool:
        """Check if a user has any active connections."""
        return bool(self._connections.get(user_id))

    @property
    def active_connections(self) -> int:
        """Total number of active connections."""
        return sum(len(conns) for conns in self._connections.values())

    @property
    def active_users(self) -> int:
        """Number of unique connected users."""
        return len(self._connections)


# Global singleton
ws_manager = ConnectionManager()


async def stream_agent_via_ws(
    websocket: WebSocket,
    user_id: str,
    agent_stream: AsyncGenerator[str, None],
) -> None:
    """
    Bridge: consume an SSE agent stream and forward events via WebSocket.

    Translates SSE `data: {...}` lines into WebSocket JSON messages,
    maintaining the same event protocol for frontend compatibility.
    """
    try:
        async for sse_line in agent_stream:
            if not sse_line or not sse_line.startswith("data: "):
                continue

            data_str = sse_line[6:].strip()
            if data_str == "[DONE]":
                await websocket.send_json({"type": "done"})
                break

            try:
                payload = json.loads(data_str)
                # Classify the event type for WebSocket clients
                if "choices" in payload:
                    await websocket.send_json({"type": "content", "data": payload})
                elif "thinking_step" in payload:
                    await websocket.send_json({"type": "thinking", "data": payload})
                elif "status" in payload:
                    await websocket.send_json({"type": "status", "data": payload})
                elif "thinking_chain_complete" in payload:
                    await websocket.send_json({"type": "chain_complete", "data": payload})
                else:
                    await websocket.send_json({"type": "data", "data": payload})
            except json.JSONDecodeError:
                continue

    except WebSocketDisconnect:
        logger.info(f"[WS] Stream disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"[WS] Stream error for user {user_id}: {e}")
        with contextlib.suppress(Exception):
            await websocket.send_json({"type": "error", "message": str(e)[:200]})
