"""
Item 36/49: Redis Pub/Sub Event Bus

Extends the existing InMemoryEventBus with Redis Pub/Sub for cross-instance
event delivery. Falls back to in-process dispatch when Redis is unavailable.
"""

import asyncio
import contextlib
import json
import logging
import os
from collections.abc import Callable

from app.services.event_bus import Event, InMemoryEventBus

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL")
REDIS_CHANNEL_PREFIX = "nexus:events:"


class RedisEventBus(InMemoryEventBus):
    """
    Event bus backed by Redis Pub/Sub for multi-instance deployments.

    - subscribe(event_type, handler) -> register local handler (same as in-memory)
    - publish(event) -> publish to Redis channel AND local queue
    - Background listener coroutine receives events from other instances
    - Graceful degradation: if Redis is unavailable, behaves as InMemoryEventBus
    """

    def __init__(self):
        super().__init__()
        self._redis = None
        self._pubsub = None
        self._listener_task: asyncio.Task | None = None
        self._redis_available = False

    async def start(self):
        """Start event processing and Redis listener."""
        await super().start()
        await self._connect_redis()
        if self._redis_available:
            self._listener_task = asyncio.create_task(self._redis_listener())
            logger.info("[RedisEventBus] Redis Pub/Sub listener started")
        else:
            logger.warning(
                "[RedisEventBus] Redis not available, running in local-only mode"
            )

    async def _connect_redis(self):
        """Try to connect to Redis for pub/sub."""
        redis_url = REDIS_URL
        if not redis_url:
            return
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(redis_url, decode_responses=True)
            # Quick connectivity check
            await self._redis.ping()
            self._pubsub = self._redis.pubsub()
            self._redis_available = True
            logger.info("[RedisEventBus] Connected to Redis")
        except ImportError:
            logger.warning("[RedisEventBus] redis package not installed")
        except Exception as e:
            logger.warning(f"[RedisEventBus] Redis connection failed: {e}")
            self._redis = None
            self._pubsub = None

    async def subscribe(self, event_type: str, handler: Callable):
        """
        Subscribe a handler to an event type.
        Also subscribes the Redis pubsub channel if Redis is available.
        """
        # Register local handler (parent class)
        super().subscribe(event_type, handler)

        # Subscribe Redis channel
        if self._redis_available and self._pubsub:
            channel = f"{REDIS_CHANNEL_PREFIX}{event_type}"
            try:
                await self._pubsub.subscribe(channel)
            except Exception as e:
                logger.warning(
                    f"[RedisEventBus] Failed to subscribe Redis channel {channel}: {e}"
                )

    def subscribe_sync(self, event_type: str, handler: Callable):
        """
        Synchronous subscribe (for @on decorator compatibility).
        Redis channel subscription will happen lazily in the listener.
        """
        super().subscribe(event_type, handler)

    async def publish(self, event: Event):
        """
        Publish event to both local queue and Redis channel.
        """
        # Always process locally
        await super().publish(event)

        # Also publish to Redis for cross-instance delivery
        if self._redis_available and self._redis:
            channel = f"{REDIS_CHANNEL_PREFIX}{event.type}"
            try:
                payload = json.dumps(event.to_dict(), default=str)
                await self._redis.publish(channel, payload)
            except Exception as e:
                logger.warning(f"[RedisEventBus] Redis publish failed: {e}")

    async def _redis_listener(self):
        """
        Background coroutine that listens for events from Redis Pub/Sub
        and dispatches them to local handlers.
        """
        # Subscribe to all event channels using pattern
        pattern_channel = f"{REDIS_CHANNEL_PREFIX}*"
        try:
            await self._pubsub.psubscribe(pattern_channel)
        except Exception as e:
            logger.error(f"[RedisEventBus] Pattern subscribe failed: {e}")
            return

        logger.info(f"[RedisEventBus] Listening on pattern: {pattern_channel}")

        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message is None:
                    await asyncio.sleep(0.1)
                    continue

                if message["type"] not in ("pmessage", "message"):
                    continue

                data = message.get("data")
                if not data or not isinstance(data, str):
                    continue

                try:
                    event_dict = json.loads(data)
                    event = Event.from_dict(event_dict)
                except (json.JSONDecodeError, TypeError, KeyError) as e:
                    logger.warning(f"[RedisEventBus] Invalid event data: {e}")
                    continue

                # Dispatch to local handlers (don't re-publish to avoid loops)
                handlers = self._handlers.get(event.type, [])
                handlers += self._handlers.get("*", [])

                if handlers:
                    await asyncio.gather(
                        *[self._safe_handle(h, event) for h in handlers],
                        return_exceptions=True,
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[RedisEventBus] Listener error: {e}")
                await asyncio.sleep(1)

    async def stop(self):
        """Stop Redis listener and event processing."""
        if self._listener_task:
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task
            self._listener_task = None

        if self._pubsub:
            with contextlib.suppress(Exception):
                await self._pubsub.unsubscribe()
                await self._pubsub.punsubscribe()
                await self._pubsub.close()

        if self._redis:
            with contextlib.suppress(Exception):
                await self._redis.close()

        await super().stop()
        logger.info("[RedisEventBus] Stopped")

    @property
    def is_redis_connected(self) -> bool:
        return self._redis_available


# ---------------------------------------------------------------------------
# Singleton: drop-in replacement for the in-memory event_bus
# ---------------------------------------------------------------------------
redis_event_bus = RedisEventBus()
