"""
Redis-based Distributed Lock for Celery Beat.

Ensures only one Celery Beat scheduler instance runs across multiple
deployments, preventing duplicate periodic task execution.

Uses Redis SET NX EX pattern:
- Lock key: celery:beat:lock
- Default TTL: 60 seconds
- Renewal: every 30 seconds (via a background thread)
- Automatic failover: if the lock holder crashes, TTL expires and another
  instance acquires the lock.

Usage in celery_app.py:
    celery_app.conf.beat_scheduler = "app.core.beat_lock.BeatLockScheduler"
"""

import logging
import os
import threading
import time
import uuid

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
LOCK_KEY = "celery:beat:lock"
LOCK_TTL = int(os.getenv("CELERY_BEAT_LOCK_TTL", "60"))
RENEW_INTERVAL = LOCK_TTL // 2  # Renew halfway through TTL


class BeatDistributedLock:
    """
    Redis-based distributed lock using SET NX EX.

    Only one process across all instances can hold the lock at a time.
    The holder renews it periodically; if it crashes, the TTL expires
    and another instance takes over.
    """

    def __init__(self, redis_url: str | None = None, lock_key: str = LOCK_KEY,
                 ttl: int = LOCK_TTL):
        self._redis_url = redis_url or REDIS_URL
        self._lock_key = lock_key
        self._ttl = ttl
        self._renew_interval = ttl // 2
        self._owner_id = f"beat-{uuid.uuid4().hex[:12]}"
        self._redis = None
        self._held = False
        self._renew_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def _get_redis(self):
        """Lazy-init synchronous Redis client."""
        if self._redis is None:
            import redis
            self._redis = redis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
            )
        return self._redis

    def acquire(self) -> bool:
        """
        Try to acquire the distributed lock.

        Returns True if this instance now holds the lock.
        """
        try:
            r = self._get_redis()
            # SET key value NX EX ttl — atomic acquire
            acquired = r.set(
                self._lock_key, self._owner_id, nx=True, ex=self._ttl
            )
            if acquired:
                self._held = True
                self._start_renew()
                logger.info(
                    f"[BeatLock] Acquired lock (owner={self._owner_id}, "
                    f"ttl={self._ttl}s)"
                )
                return True

            # Check who holds it (for logging)
            current_owner = r.get(self._lock_key)
            logger.debug(
                f"[BeatLock] Lock held by {current_owner}, "
                f"this instance ({self._owner_id}) will wait"
            )
            return False

        except Exception as e:
            logger.error(f"[BeatLock] Failed to acquire lock: {e}")
            return False

    def release(self) -> None:
        """Release the lock if held by this instance."""
        self._stop_renew()
        if not self._held:
            return

        try:
            r = self._get_redis()
            # Only release if we still own it (Lua script for atomicity)
            lua = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            result = r.eval(lua, 1, self._lock_key, self._owner_id)
            if result:
                logger.info(f"[BeatLock] Released lock (owner={self._owner_id})")
            self._held = False
        except Exception as e:
            logger.error(f"[BeatLock] Failed to release lock: {e}")
            self._held = False

    def _start_renew(self) -> None:
        """Start background thread to renew the lock TTL."""
        self._stop_event.clear()
        self._renew_thread = threading.Thread(
            target=self._renew_loop, daemon=True, name="beat-lock-renew"
        )
        self._renew_thread.start()

    def _stop_renew(self) -> None:
        """Signal the renewal thread to stop."""
        self._stop_event.set()
        if self._renew_thread and self._renew_thread.is_alive():
            self._renew_thread.join(timeout=5)
        self._renew_thread = None

    def _renew_loop(self) -> None:
        """Periodically renew the lock TTL while held."""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._renew_interval)
            if self._stop_event.is_set():
                break
            try:
                r = self._get_redis()
                # Only renew if we still own the lock
                lua = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("expire", KEYS[1], ARGV[2])
                else
                    return 0
                end
                """
                result = r.eval(
                    lua, 1, self._lock_key, self._owner_id, str(self._ttl)
                )
                if result:
                    logger.debug(
                        f"[BeatLock] Renewed lock TTL "
                        f"(owner={self._owner_id}, ttl={self._ttl}s)"
                    )
                else:
                    logger.warning(
                        "[BeatLock] Lock lost — another instance took over"
                    )
                    self._held = False
                    break
            except Exception as e:
                logger.error(f"[BeatLock] Renewal failed: {e}")

    @property
    def is_held(self) -> bool:
        return self._held

    @property
    def owner_id(self) -> str:
        return self._owner_id


class BeatLockScheduler:
    """
    Drop-in Celery Beat scheduler wrapper that enforces distributed locking.

    Only the instance holding the Redis lock will actually tick the
    scheduler. Others block-wait and attempt to acquire the lock
    periodically.

    Configure in celery:
        celery_app.conf.beat_scheduler = "app.core.beat_lock.BeatLockScheduler"
    """

    def __init__(self, *args, **kwargs):
        # Import here to avoid circular import at module level
        from celery.beat import PersistentScheduler

        self._lock = BeatDistributedLock()
        self._inner = PersistentScheduler(*args, **kwargs)
        self._acquire_interval = 5  # seconds between lock attempts

    def setup_schedule(self):
        return self._inner.setup_schedule()

    def tick(self):
        """
        Core scheduler tick.

        If we hold the lock: delegate to the inner scheduler.
        If not: try to acquire the lock, sleep briefly if we can't.
        """
        if self._lock.is_held:
            return self._inner.tick()

        # Try to acquire
        if self._lock.acquire():
            return self._inner.tick()

        # Could not acquire — wait before retrying
        logger.debug(
            f"[BeatLock] Waiting for lock "
            f"(retry in {self._acquire_interval}s)"
        )
        return self._acquire_interval

    def close(self):
        self._lock.release()
        return self._inner.close()

    @property
    def schedule(self):
        return self._inner.schedule

    @schedule.setter
    def schedule(self, value):
        self._inner.schedule = value

    @property
    def info(self):
        return self._inner.info

    def sync(self):
        return self._inner.sync()

    @property
    def should_sync(self):
        return self._inner.should_sync

    def get_schedule(self):
        return self._inner.get_schedule()

    def set_schedule(self, schedule):
        return self._inner.set_schedule(schedule)

    def update_schedule(self, mapping):
        return self._inner.update_schedule(mapping)

    def merge_inplace(self, schedule):
        return self._inner.merge_inplace(schedule)

    def apply_entry(self, entry, producer=None):
        return self._inner.apply_entry(entry, producer=producer)

    def maybe_due(self, entry, **kwargs):
        return self._inner.maybe_due(entry, **kwargs)
