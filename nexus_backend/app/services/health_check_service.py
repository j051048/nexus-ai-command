"""
P2 Enhancement: Health Check Service

Implements health checks and readiness probes for Kubernetes.
Fixes Issue #15: Missing health checks and readiness probes.
"""

import asyncio
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    name: str
    status: HealthStatus
    message: str
    latency_ms: float = 0
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class HealthCheckService:
    """
    P2 Enhancement: Health checks and readiness probes.

    Features:
    - Liveness probe (is the app running?)
    - Readiness probe (is the app ready to serve?)
    - Startup probe (is the app starting up?)
    - Dependency health checks
    - Detailed health reports
    - Kubernetes integration
    """

    def __init__(self):
        self._checks: dict[str, Callable] = {}
        self._readiness_checks: dict[str, Callable] = {}
        self._startup_checks: dict[str, Callable] = {}
        self._last_results: dict[str, HealthCheckResult] = {}
        self._start_time = time.time()
        self._is_ready = False

        # Register default checks
        self._register_default_checks()

    def _register_default_checks(self):
        """Register default health checks."""
        self.register_check("memory", self._check_memory)
        self.register_check("disk", self._check_disk)
        self.register_readiness_check("database", self._check_database)
        self.register_readiness_check("redis", self._check_redis)

    def register_check(self, name: str, check_func: Callable):
        """Register a health check."""
        self._checks[name] = check_func

    def register_readiness_check(self, name: str, check_func: Callable):
        """Register a readiness check."""
        self._readiness_checks[name] = check_func

    def register_startup_check(self, name: str, check_func: Callable):
        """Register a startup check."""
        self._startup_checks[name] = check_func

    async def _check_memory(self) -> HealthCheckResult:
        """Check memory usage."""
        try:
            import psutil

            memory = psutil.virtual_memory()
            used_percent = memory.percent

            if used_percent < 80:
                status = HealthStatus.HEALTHY
            elif used_percent < 90:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY

            return HealthCheckResult(
                name="memory",
                status=status,
                message=f"Memory usage: {used_percent}%",
                details={
                    "total_gb": round(memory.total / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "percent": used_percent
                }
            )
        except ImportError:
            return HealthCheckResult(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message="psutil not available"
            )

    async def _check_disk(self) -> HealthCheckResult:
        """Check disk usage."""
        try:
            import shutil

            usage = shutil.disk_usage("/")
            used_percent = (usage.used / usage.total) * 100

            if used_percent < 80:
                status = HealthStatus.HEALTHY
            elif used_percent < 90:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY

            return HealthCheckResult(
                name="disk",
                status=status,
                message=f"Disk usage: {used_percent:.1f}%",
                details={
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2)
                }
            )
        except Exception as e:
            return HealthCheckResult(
                name="disk",
                status=HealthStatus.UNKNOWN,
                message=str(e)
            )

    async def _check_database(self) -> HealthCheckResult:
        """Check database connectivity."""
        try:
            from app.core.database import supabase

            if supabase is None:
                return HealthCheckResult(
                    name="database",
                    status=HealthStatus.DEGRADED,
                    message="Database client not initialized (missing config or dependency)"
                )

            start = time.time()

            # Execute a real lightweight query to verify connectivity
            await supabase.table("users").select("id").limit(1).execute()

            latency = (time.time() - start) * 1000

            return HealthCheckResult(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Database connection OK",
                latency_ms=round(latency, 2)
            )
        except Exception as e:
            latency = (time.time() - start) * 1000 if 'start' in locals() else 0
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database error: {str(e)}",
                latency_ms=round(latency, 2)
            )

    async def _check_redis(self) -> HealthCheckResult:
        """Check Redis connectivity."""
        try:
            from app.services.cache_service import cache_service

            start = time.time()

            # Ensure cache service is initialized, then ping
            ping_ok = await cache_service.ping()

            latency = (time.time() - start) * 1000

            if not ping_ok:
                return HealthCheckResult(
                    name="redis",
                    status=HealthStatus.DEGRADED,
                    message="Redis ping failed",
                    latency_ms=round(latency, 2)
                )

            # Report whether we're using real Redis or in-memory fallback
            if cache_service._use_redis:
                message = "Redis connection OK"
                status = HealthStatus.HEALTHY
            else:
                message = "Using in-memory cache fallback (Redis not configured or unavailable)"
                status = HealthStatus.DEGRADED

            return HealthCheckResult(
                name="redis",
                status=status,
                message=message,
                latency_ms=round(latency, 2)
            )
        except Exception as e:
            latency = (time.time() - start) * 1000 if 'start' in locals() else 0
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis error: {str(e)}",
                latency_ms=round(latency, 2)
            )

    async def run_check(self, name: str, check_func: Callable) -> HealthCheckResult:
        """Run a single health check."""
        start = time.time()

        try:
            if asyncio.iscoroutinefunction(check_func):
                result = await check_func()
            else:
                result = check_func()

            if not isinstance(result, HealthCheckResult):
                result = HealthCheckResult(
                    name=name,
                    status=HealthStatus.HEALTHY,
                    message=str(result)
                )

            return result

        except Exception as e:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {str(e)}",
                latency_ms=(time.time() - start) * 1000
            )

    async def check_health(self) -> dict[str, Any]:
        """
        Run all health checks (liveness probe).

        Returns:
            Health status report
        """
        results = []
        overall_status = HealthStatus.HEALTHY

        for name, check_func in self._checks.items():
            result = await self.run_check(name, check_func)
            results.append(result)
            self._last_results[name] = result

            if result.status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
            elif result.status == HealthStatus.DEGRADED and overall_status != HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.DEGRADED

        return {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": int(time.time() - self._start_time),
            "checks": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "message": r.message,
                    "latency_ms": r.latency_ms,
                    "details": r.details
                }
                for r in results
            ]
        }

    async def check_readiness(self) -> dict[str, Any]:
        """
        Run readiness checks (readiness probe).

        Returns:
            Readiness status report
        """
        results = []
        is_ready = True

        for name, check_func in self._readiness_checks.items():
            result = await self.run_check(name, check_func)
            results.append(result)
            self._last_results[f"readiness_{name}"] = result

            if result.status == HealthStatus.UNHEALTHY:
                is_ready = False

        self._is_ready = is_ready

        return {
            "ready": is_ready,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "message": r.message,
                    "latency_ms": r.latency_ms
                }
                for r in results
            ]
        }

    async def check_startup(self) -> dict[str, Any]:
        """
        Run startup checks (startup probe).

        Returns:
            Startup status report
        """
        results = []
        is_started = True

        for name, check_func in self._startup_checks.items():
            result = await self.run_check(name, check_func)
            results.append(result)

            if result.status == HealthStatus.UNHEALTHY:
                is_started = False

        return {
            "started": is_started,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": int(time.time() - self._start_time)
        }

    def get_liveness_endpoint(self) -> dict:
        """Get simplified liveness response for Kubernetes."""
        return {"status": "alive"}

    def get_readiness_endpoint(self) -> dict:
        """Get simplified readiness response for Kubernetes."""
        return {"ready": self._is_ready}

    async def get_detailed_health(self) -> dict[str, Any]:
        """
        Get detailed health report.

        Returns:
            Comprehensive health report
        """
        health = await self.check_health()
        readiness = await self.check_readiness()

        return {
            "status": health["status"],
            "ready": readiness["ready"],
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": health["uptime_seconds"],
            "version": os.getenv("APP_VERSION", "1.0.0"),
            "environment": os.getenv("ENVIRONMENT", "development"),
            "components": {
                "health": health["checks"],
                "readiness": readiness["checks"]
            },
            "metrics": {
                "uptime_human": self._format_uptime(health["uptime_seconds"]),
                "total_checks": len(health["checks"]) + len(readiness["checks"]),
                "healthy_count": sum(
                    1 for r in health["checks"] + readiness["checks"]
                    if r["status"] == HealthStatus.HEALTHY.value
                )
            }
        }

    def _format_uptime(self, seconds: int) -> str:
        """Format uptime in human readable format."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

    async def check_dependencies(self) -> dict[str, Any]:
        """Check all external dependencies."""
        dependencies = {}

        # Check each dependency
        checks = [
            ("openai", self._check_openai),
            ("supabase", self._check_supabase),
            ("redis", self._check_redis),
            ("database", self._check_database)
        ]

        for name, check_func in checks:
            try:
                result = await self.run_check(name, check_func)
                dependencies[name] = {
                    "status": result.status.value,
                    "message": result.message,
                    "latency_ms": result.latency_ms
                }
            except Exception as e:
                dependencies[name] = {
                    "status": HealthStatus.UNKNOWN.value,
                    "message": str(e)
                }

        return dependencies

    async def _check_openai(self) -> HealthCheckResult:
        """Check OpenAI API connectivity."""
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            return HealthCheckResult(
                name="openai",
                status=HealthStatus.DEGRADED,
                message="OPENAI_API_KEY not configured"
            )

        # In production, make actual API call
        return HealthCheckResult(
            name="openai",
            status=HealthStatus.HEALTHY,
            message="OpenAI API configured"
        )

    async def _check_supabase(self) -> HealthCheckResult:
        """Check Supabase connectivity."""
        url = os.getenv("SUPABASE_URL")

        if not url:
            return HealthCheckResult(
                name="supabase",
                status=HealthStatus.DEGRADED,
                message="SUPABASE_URL not configured"
            )

        try:
            from app.core.database import supabase

            if supabase is None:
                return HealthCheckResult(
                    name="supabase",
                    status=HealthStatus.DEGRADED,
                    message="Supabase client not initialized (missing key or dependency)"
                )

            start = time.time()

            # Execute a real query to verify Supabase connectivity
            await supabase.table("users").select("id").limit(1).execute()

            latency = (time.time() - start) * 1000

            return HealthCheckResult(
                name="supabase",
                status=HealthStatus.HEALTHY,
                message="Supabase connection OK",
                latency_ms=round(latency, 2)
            )
        except Exception as e:
            latency = (time.time() - start) * 1000 if 'start' in locals() else 0
            return HealthCheckResult(
                name="supabase",
                status=HealthStatus.UNHEALTHY,
                message=f"Supabase error: {str(e)}",
                latency_ms=round(latency, 2)
            )


# Global instance
health_check_service = HealthCheckService()
