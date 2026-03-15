"""
WebSocket Connection Manager — enables server-push and bidirectional communication.

Manages WebSocket connections per user, supports:
- Server-initiated push (proactive notifications, trigger results)
- Real-time agent streaming via WebSocket (alternative to SSE)
- Connection lifecycle management with heartbeat
- Per-user and global connection limits
"""

import asyncio
import contextlib
import json
import logging
import os
import time
from collections.abc import AsyncGenerator

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# Connection limits (configurable via env)
MAX_CONNECTIONS_PER_USER = int(os.getenv("WS_MAX_PER_USER", "5"))
MAX_CONNECTIONS_GLOBAL = int(os.getenv("WS_MAX_GLOBAL", "1000"))
HEARTBEAT_INTERVAL = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))


class ConnectionManager:
    """
    Manages active WebSocket connections keyed by user_id.

    Thread-safe for asyncio: all mutations happen in the event loop.
    Supports multiple connections per user (e.g., multiple browser tabs).

    Limits:
    - Per-user: MAX_CONNECTIONS_PER_USER (default 5)
    - Global: MAX_CONNECTIONS_GLOBAL (default 1000)
    - Heartbeat: pings every HEARTBEAT_INTERVAL seconds to detect stale connections
    """

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._last_pong: dict[int, float] = {}  # ws id -> last pong time
        self._heartbeat_task: asyncio.Task | None = None

    async def connect(self, websocket: WebSocket, user_id: str) -> bool:
        """
        Accept and register a WebSocket connection.

        Returns False if connection limits are exceeded (caller should close).
        """
        # Global limit check
        if self.active_connections >= MAX_CONNECTIONS_GLOBAL:
            logger.warning(f"[WS] Global connection limit reached ({MAX_CONNECTIONS_GLOBAL}), rejecting user {user_id}")
            await websocket.close(code=1013, reason="Server at capacity")
            return False

        # Per-user limit check
        user_conns = self._connections.get(user_id, [])
        if len(user_conns) >= MAX_CONNECTIONS_PER_USER:
            logger.warning(
                f"[WS] Per-user limit reached ({MAX_CONNECTIONS_PER_USER}) "
                f"for user {user_id}, closing oldest connection"
            )
            # Evict the oldest connection instead of rejecting
            oldest = user_conns[0]
            with contextlib.suppress(Exception):
                await oldest.close(code=4002, reason="Replaced by new connection")
            self.disconnect(oldest, user_id)

        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)
        self._last_pong[id(websocket)] = time.time()
        logger.info(
            f"[WS] User {user_id} connected "
            f"(user: {len(self._connections[user_id])}, global: {self.active_connections})"
        )

        # Start heartbeat if not running
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        return True

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        """Remove a WebSocket connection."""
        if user_id in self._connections:
            self._connections[user_id] = [ws for ws in self._connections[user_id] if ws is not websocket]
            if not self._connections[user_id]:
                del self._connections[user_id]
        self._last_pong.pop(id(websocket), None)
        logger.info(f"[WS] User {user_id} disconnected (global: {self.active_connections})")

    def record_pong(self, websocket: WebSocket) -> None:
        """Record pong response from a client."""
        self._last_pong[id(websocket)] = time.time()

    async def _heartbeat_loop(self) -> None:
        """Periodically ping all connections and evict stale ones."""
        while self.active_connections > 0:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            stale_timeout = HEARTBEAT_INTERVAL * 3  # 3 missed pongs = stale
            now = time.time()
            stale_pairs: list[tuple[str, WebSocket]] = []

            for user_id, connections in list(self._connections.items()):
                for ws in connections:
                    last = self._last_pong.get(id(ws), 0)
                    if now - last > stale_timeout:
                        stale_pairs.append((user_id, ws))
                    else:
                        # Send ping
                        try:
                            await ws.send_json({"type": "ping", "ts": int(now)})
                        except Exception:
                            stale_pairs.append((user_id, ws))

            # Evict stale connections
            for user_id, ws in stale_pairs:
                logger.info(f"[WS] Evicting stale connection for user {user_id}")
                with contextlib.suppress(Exception):
                    await ws.close(code=4003, reason="Heartbeat timeout")
                self.disconnect(ws, user_id)

        logger.debug("[WS] Heartbeat loop ended — no active connections")

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

    def get_connected_user_ids(self) -> list[str]:
        """Return list of currently connected user IDs."""
        return [uid for uid, conns in self._connections.items() if conns]

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
