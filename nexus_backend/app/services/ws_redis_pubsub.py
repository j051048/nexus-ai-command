"""
Redis Pub/Sub Adapter for WebSocket cross-instance message broadcasting.

Enables multiple backend instances to deliver WebSocket messages to any
connected user regardless of which instance holds the actual connection.

Channel naming:
- ws:user:{user_id}  — messages targeting a specific user
- ws:broadcast       — messages for all connected users

Falls back to local-only delivery when Redis is unavailable.
"""

import asyncio
import contextlib
import json
import logging
import os
import time
from collections.abc import Callable, Coroutine
from typing import Any

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CHANNEL_PREFIX = "ws:user:"
BROADCAST_CHANNEL = "ws:broadcast"
HEALTH_CHECK_INTERVAL = int(os.getenv("WS_REDIS_HEALTH_INTERVAL", "30"))


class RedisWebSocketBridge:
    """
    Bridges WebSocket connections across multiple backend instances via
    Redis Pub/Sub.

    Usage:
        bridge = RedisWebSocketBridge()
        await bridge.start()

        # When a user connects on this instance
        await bridge.subscribe("user-123", local_deliver_callback)

        # When any code wants to push to a user (may be on another instance)
        await bridge.publish("user-123", {"type": "notification", ...})

        # Cleanup
        await bridge.stop()
    """

    def __init__(self, redis_url: str | None = None):
        self._redis_url = redis_url or REDIS_URL
        self._redis = None  # redis.asyncio.Redis
        self._pubsub = None  # redis.asyncio.PubSub
        self._listener_task: asyncio.Task | None = None
        self._health_task: asyncio.Task | None = None
        self._available = False
        self._subscriptions: dict[str, Callable[[dict], Coroutine]] = {}
        self._broadcast_callback: Callable[[dict, str | None], Coroutine] | None = None
        self._last_health_ok: float = 0.0
        self._lock = asyncio.Lock()

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def start(self) -> bool:
        """Initialize Redis connection and start listener. Returns True if OK."""
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                retry_on_timeout=True,
            )
            # Verify connectivity
            await self._redis.ping()
            self._pubsub = self._redis.pubsub()
            self._available = True
            self._last_health_ok = time.time()

            # Start background listener
            self._listener_task = asyncio.create_task(
                self._listen_loop(), name="ws-redis-listener"
            )
            # Start health monitor
            self._health_task = asyncio.create_task(
                self._health_loop(), name="ws-redis-health"
            )

            logger.info("[WS-Redis] Pub/Sub bridge started successfully")
            return True

        except ImportError:
            logger.warning("[WS-Redis] redis package not installed, running local-only")
            return False
        except Exception as e:
            logger.warning(f"[WS-Redis] Failed to connect to Redis: {e}, running local-only")
            self._available = False
            return False

    async def stop(self) -> None:
        """Clean shutdown of Redis connections and background tasks."""
        self._available = False

        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task

        if self._health_task and not self._health_task.done():
            self._health_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._health_task

        if self._pubsub:
            try:
                await self._pubsub.unsubscribe()
                await self._pubsub.close()
            except Exception:
                pass

        if self._redis:
            with contextlib.suppress(Exception):
                await self._redis.close()

        logger.info("[WS-Redis] Pub/Sub bridge stopped")

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        return self._available

    async def publish(self, user_id: str, message: dict) -> bool:
        """
        Publish a message to a user's Redis channel.

        All instances subscribed to this user's channel will receive it
        and deliver to local connections.

        Returns True if published to Redis, False on failure.
        """
        if not self._available:
            return False

        channel = f"{CHANNEL_PREFIX}{user_id}"
        try:
            payload = json.dumps(message, ensure_ascii=False, default=str)
            await self._redis.publish(channel, payload)
            return True
        except Exception as e:
            logger.warning(f"[WS-Redis] Publish failed for user {user_id}: {e}")
            return False

    async def publish_broadcast(
        self, message: dict, exclude_user: str | None = None
    ) -> bool:
        """
        Publish a broadcast message to the global channel.

        All instances will receive and deliver to every connected user.
        """
        if not self._available:
            return False

        try:
            payload = json.dumps(
                {"message": message, "exclude_user": exclude_user},
                ensure_ascii=False,
                default=str,
            )
            await self._redis.publish(BROADCAST_CHANNEL, payload)
            return True
        except Exception as e:
            logger.warning(f"[WS-Redis] Broadcast publish failed: {e}")
            return False

    async def subscribe(
        self,
        user_id: str,
        callback: Callable[[dict], Coroutine],
    ) -> None:
        """
        Subscribe to a user's channel so this instance can deliver messages
        from other instances to local connections.

        Args:
            user_id: The user whose channel to subscribe to.
            callback: async function(message_dict) to deliver locally.
        """
        async with self._lock:
            self._subscriptions[user_id] = callback

        if not self._available or not self._pubsub:
            return

        channel = f"{CHANNEL_PREFIX}{user_id}"
        try:
            await self._pubsub.subscribe(channel)
            logger.debug(f"[WS-Redis] Subscribed to channel {channel}")
        except Exception as e:
            logger.warning(f"[WS-Redis] Subscribe failed for {channel}: {e}")

    async def unsubscribe(self, user_id: str) -> None:
        """Unsubscribe from a user's channel (e.g., when last connection drops)."""
        async with self._lock:
            self._subscriptions.pop(user_id, None)

        if not self._available or not self._pubsub:
            return

        channel = f"{CHANNEL_PREFIX}{user_id}"
        try:
            await self._pubsub.unsubscribe(channel)
            logger.debug(f"[WS-Redis] Unsubscribed from channel {channel}")
        except Exception as e:
            logger.warning(f"[WS-Redis] Unsubscribe failed for {channel}: {e}")

    def set_broadcast_callback(
        self, callback: Callable[[dict, str | None], Coroutine]
    ) -> None:
        """
        Register a callback for broadcast messages.

        Args:
            callback: async function(message_dict, exclude_user) to deliver.
        """
        self._broadcast_callback = callback

    async def subscribe_broadcast(self) -> None:
        """Subscribe to the global broadcast channel."""
        if not self._available or not self._pubsub:
            return
        try:
            await self._pubsub.subscribe(BROADCAST_CHANNEL)
            logger.debug("[WS-Redis] Subscribed to broadcast channel")
        except Exception as e:
            logger.warning(f"[WS-Redis] Broadcast subscribe failed: {e}")

    # ── Background Loops ─────────────────────────────────────────────────

    async def _listen_loop(self) -> None:
        """
        Main listener: reads messages from all subscribed Redis channels
        and dispatches to the appropriate local callback.
        """
        logger.info("[WS-Redis] Listener loop started")
        while self._available:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message is None:
                    await asyncio.sleep(0.05)
                    continue

                if message["type"] != "message":
                    continue

                channel: str = message["channel"]
                raw_data: str = message["data"]

                try:
                    data = json.loads(raw_data)
                except (json.JSONDecodeError, TypeError):
                    continue

                # Dispatch based on channel type
                if channel == BROADCAST_CHANNEL:
                    if self._broadcast_callback:
                        msg = data.get("message", data)
                        exclude = data.get("exclude_user")
                        asyncio.create_task(
                            self._safe_callback(
                                self._broadcast_callback, msg, exclude
                            )
                        )
                elif channel.startswith(CHANNEL_PREFIX):
                    user_id = channel[len(CHANNEL_PREFIX):]
                    callback = self._subscriptions.get(user_id)
                    if callback:
                        asyncio.create_task(
                            self._safe_callback(callback, data)
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[WS-Redis] Listener error: {e}")
                await asyncio.sleep(1)

        logger.info("[WS-Redis] Listener loop ended")

    async def _health_loop(self) -> None:
        """Periodically check Redis connectivity."""
        while self._available:
            try:
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
                if self._redis:
                    await self._redis.ping()
                    self._last_health_ok = time.time()
            except asyncio.CancelledError:
                break
            except Exception as e:
                elapsed = time.time() - self._last_health_ok
                logger.warning(
                    f"[WS-Redis] Health check failed "
                    f"(last OK {elapsed:.0f}s ago): {e}"
                )
                if elapsed > HEALTH_CHECK_INTERVAL * 3:
                    logger.error(
                        "[WS-Redis] Redis unreachable for too long, "
                        "marking bridge unavailable"
                    )
                    self._available = False

    @staticmethod
    async def _safe_callback(callback: Callable, *args: Any) -> None:
        """Execute a callback with error isolation."""
        try:
            await callback(*args)
        except Exception as e:
            logger.error(f"[WS-Redis] Callback error: {e}")

    # ── Diagnostics ──────────────────────────────────────────────────────

    def status(self) -> dict:
        """Return current bridge status for health checks."""
        return {
            "available": self._available,
            "subscribed_users": list(self._subscriptions.keys()),
            "last_health_ok": self._last_health_ok,
            "listener_running": (
                self._listener_task is not None
                and not self._listener_task.done()
            ),
        }
