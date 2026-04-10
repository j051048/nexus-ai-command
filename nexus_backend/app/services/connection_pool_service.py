"""
P2 Enhancement: Connection Pool Management Service

Implements centralized connection pooling for database and external services.
Fixes Issue #37: Missing connection pool management.
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PoolStats:
    """Connection pool statistics."""

    pool_name: str
    total_connections: int
    active_connections: int
    idle_connections: int
    waiting_requests: int
    avg_wait_time_ms: float
    created_at: str


class ConnectionPoolService:
    """
    P2 Enhancement: Centralized connection pool management.

    Features:
    - Database connection pooling
    - HTTP client connection pooling
    - Redis connection pooling
    - Pool health monitoring
    - Automatic connection recycling
    - Connection leak detection
    """

    def __init__(
        self,
        db_pool_size: int = 10,
        db_max_overflow: int = 20,
        http_pool_size: int = 100,
        redis_pool_size: int = 10,
        pool_recycle_seconds: int = 3600,
    ):
        self.db_pool_size = db_pool_size
        self.db_max_overflow = db_max_overflow
        self.http_pool_size = http_pool_size
        self.redis_pool_size = redis_pool_size
        self.pool_recycle_seconds = pool_recycle_seconds

        self._db_pool = None
        self._http_client = None
        self._redis_pool = None
        self._pool_stats: dict[str, PoolStats] = {}
        self._connection_times: dict[str, float] = {}

    async def init_db_pool(self, database_url: str = None):
        """
        Initialize database connection pool.
        Uses asyncpg for PostgreSQL.
        """
        database_url = database_url or os.getenv("DATABASE_URL")
        if not database_url:
            logger.warning("DATABASE_URL not set, skipping DB pool init")
            return

        try:
            import asyncpg

            self._db_pool = await asyncpg.create_pool(
                database_url,
                min_size=self.db_pool_size,
                max_size=self.db_pool_size + self.db_max_overflow,
                command_timeout=60,
                max_inactive_connection_lifetime=self.pool_recycle_seconds,
            )

            self._pool_stats["database"] = PoolStats(
                pool_name="database",
                total_connections=self.db_pool_size + self.db_max_overflow,
                active_connections=0,
                idle_connections=self.db_pool_size,
                waiting_requests=0,
                avg_wait_time_ms=0,
                created_at=datetime.utcnow().isoformat(),
            )

            logger.info(
                f"Database pool initialized: size={self.db_pool_size}, max={self.db_pool_size + self.db_max_overflow}"
            )

        except ImportError:
            logger.warning("asyncpg not installed, using default connection")
        except Exception as e:
            logger.error(f"Failed to initialize DB pool: {e}")

    async def init_http_pool(self):
        """
        Initialize HTTP connection pool.
        Uses aiohttp with connection pooling.
        """
        try:
            import aiohttp

            connector = aiohttp.TCPConnector(
                limit=self.http_pool_size,
                limit_per_host=20,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
            )

            timeout = aiohttp.ClientTimeout(total=60, connect=10, sock_read=30)

            self._http_client = aiohttp.ClientSession(
                connector=connector, timeout=timeout
            )

            self._pool_stats["http"] = PoolStats(
                pool_name="http",
                total_connections=self.http_pool_size,
                active_connections=0,
                idle_connections=self.http_pool_size,
                waiting_requests=0,
                avg_wait_time_ms=0,
                created_at=datetime.utcnow().isoformat(),
            )

            logger.info(f"HTTP pool initialized: size={self.http_pool_size}")

        except ImportError:
            logger.warning("aiohttp not installed, HTTP pooling disabled")
        except Exception as e:
            logger.error(f"Failed to initialize HTTP pool: {e}")

    async def init_redis_pool(self, redis_url: str = None):
        """
        Initialize Redis connection pool.
        """
        redis_url = redis_url or os.getenv("REDIS_URL")
        if not redis_url:
            logger.info("REDIS_URL not set, skipping Redis pool init")
            return

        try:
            import redis.asyncio as redis

            self._redis_pool = redis.ConnectionPool.from_url(
                redis_url, max_connections=self.redis_pool_size, decode_responses=True
            )

            self._pool_stats["redis"] = PoolStats(
                pool_name="redis",
                total_connections=self.redis_pool_size,
                active_connections=0,
                idle_connections=self.redis_pool_size,
                waiting_requests=0,
                avg_wait_time_ms=0,
                created_at=datetime.utcnow().isoformat(),
            )

            logger.info(f"Redis pool initialized: size={self.redis_pool_size}")

        except ImportError:
            logger.warning("redis not installed, Redis pooling disabled")
        except Exception as e:
            logger.error(f"Failed to initialize Redis pool: {e}")

    async def init_all(self, database_url: str = None, redis_url: str = None):
        """Initialize all connection pools."""
        await asyncio.gather(
            self.init_db_pool(database_url),
            self.init_http_pool(),
            self.init_redis_pool(redis_url),
        )

    @property
    def db(self):
        """Get database pool."""
        return self._db_pool

    @property
    def http(self):
        """Get HTTP client."""
        return self._http_client

    @property
    def redis(self):
        """Get Redis connection pool."""
        return self._redis_pool

    async def get_db_connection(self):
        """
        Get a database connection from the pool.
        Tracks connection time for monitoring.
        """
        if not self._db_pool:
            raise RuntimeError("Database pool not initialized")

        start_time = time.time()
        conn = await self._db_pool.acquire()
        (time.time() - start_time) * 1000

        # Track connection time
        conn_id = id(conn)
        self._connection_times[conn_id] = time.time()

        # Update stats
        if "database" in self._pool_stats:
            stats = self._pool_stats["database"]
            stats.active_connections += 1
            stats.idle_connections -= 1

        return conn

    async def release_db_connection(self, conn):
        """Release a database connection back to the pool."""
        if not self._db_pool:
            return

        conn_id = id(conn)
        acquire_time = self._connection_times.pop(conn_id, None)

        # Check for connection leak (held too long)
        if acquire_time and time.time() - acquire_time > 300:  # 5 minutes
            logger.warning(
                f"Potential connection leak: connection held for {time.time() - acquire_time:.1f}s"
            )

        await self._db_pool.release(conn)

        # Update stats
        if "database" in self._pool_stats:
            stats = self._pool_stats["database"]
            stats.active_connections -= 1
            stats.idle_connections += 1

    def get_stats(self) -> dict[str, Any]:
        """Get all pool statistics."""
        result = {}

        for name, stats in self._pool_stats.items():
            result[name] = {
                "pool_name": stats.pool_name,
                "total_connections": stats.total_connections,
                "active_connections": stats.active_connections,
                "idle_connections": stats.idle_connections,
                "waiting_requests": stats.waiting_requests,
                "created_at": stats.created_at,
            }

        # Add internal pool stats if available
        if self._db_pool:
            result["database"]["internal"] = {
                "size": (
                    self._db_pool.get_size()
                    if hasattr(self._db_pool, "get_size")
                    else None
                ),
                "idle": (
                    self._db_pool.get_idle_size()
                    if hasattr(self._db_pool, "get_idle_size")
                    else None
                ),
            }

        return result

    def get_health(self) -> dict[str, str]:
        """Get health status of all pools."""
        health = {}

        for name, stats in self._pool_stats.items():
            # Consider unhealthy if more than 80% connections in use
            utilization = stats.active_connections / max(stats.total_connections, 1)
            if utilization > 0.9:
                health[name] = "critical"
            elif utilization > 0.7:
                health[name] = "warning"
            else:
                health[name] = "healthy"

        return health

    async def close(self):
        """Close all connection pools."""
        if self._db_pool:
            await self._db_pool.close()
            logger.info("Database pool closed")

        if self._http_client:
            await self._http_client.close()
            logger.info("HTTP client closed")

        if self._redis_pool:
            await self._redis_pool.disconnect()
            logger.info("Redis pool closed")


# Global instance
connection_pool_service = ConnectionPoolService(
    db_pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
    db_max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
    http_pool_size=int(os.getenv("HTTP_POOL_SIZE", "100")),
    redis_pool_size=int(os.getenv("REDIS_POOL_SIZE", "10")),
)
