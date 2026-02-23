"""
P2 Enhancement: API Versioning Service

Implements API version control and management.
Fixes Issue #13: Missing API version control.
"""

import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class VersionStatus(Enum):
    """API version status."""

    DEVELOPMENT = "development"
    BETA = "beta"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"


@dataclass
class APIVersion:
    """API version definition."""

    version: str
    status: VersionStatus
    release_date: str
    sunset_date: str | None = None
    deprecation_date: str | None = None
    changelog: list[str] = field(default_factory=list)
    breaking_changes: list[str] = field(default_factory=list)
    endpoints: dict[str, str] = field(default_factory=dict)


class APIVersioningService:
    """
    P2 Enhancement: API version management.

    Features:
    - Multiple versioning strategies (URL, Header, Query)
    - Version lifecycle management
    - Deprecation warnings
    - Sunset notifications
    - Version routing
    """

    # Versioning strategies
    VERSION_STRATEGIES = {
        "url",  # /v1/users, /v2/users
        "header",  # X-API-Version: 1
        "query",  # ?version=1
        "content_type",  # Accept: application/vnd.api+json;version=1
    }

    def __init__(self, default_version: str = "1.0", strategy: str = "url"):
        self.default_version = default_version
        self.strategy = strategy
        self._versions: dict[str, APIVersion] = {}
        self._version_handlers: dict[str, Callable] = {}
        self._migration_handlers: dict[str, Callable] = {}

        # Initialize default versions
        self._init_default_versions()

    def _init_default_versions(self):
        """Initialize default API versions."""
        self.register_version(
            APIVersion(
                version="1.0",
                status=VersionStatus.STABLE,
                release_date="2024-01-01",
                changelog=["Initial API release", "Core endpoints for chat, documents, users"],
            )
        )

        self.register_version(
            APIVersion(
                version="1.1",
                status=VersionStatus.STABLE,
                release_date="2024-06-01",
                changelog=["Added streaming support", "Added multimodal endpoints", "Improved error responses"],
            )
        )

        self.register_version(
            APIVersion(
                version="2.0",
                status=VersionStatus.BETA,
                release_date="2024-12-01",
                changelog=["New Agent framework", "Enhanced RAG capabilities", "Multi-tenant improvements"],
                breaking_changes=["Changed response format for /chat endpoint", "Removed deprecated /legacy endpoints"],
            )
        )

    def register_version(self, version: APIVersion):
        """Register an API version."""
        self._versions[version.version] = version
        logger.info(f"Registered API version {version.version} ({version.status.value})")

    def register_handler(self, version: str, endpoint: str, handler: Callable):
        """Register a version-specific handler for an endpoint."""
        key = f"{version}:{endpoint}"
        self._version_handlers[key] = handler

    def register_migration(self, from_version: str, to_version: str, handler: Callable):
        """Register a migration handler between versions."""
        key = f"{from_version}->{to_version}"
        self._migration_handlers[key] = handler

    def get_version(self, version: str) -> APIVersion | None:
        """Get version details."""
        return self._versions.get(version)

    def get_latest_version(self, status: VersionStatus = None) -> APIVersion | None:
        """Get the latest version, optionally filtered by status."""
        versions = list(self._versions.values())

        if status:
            versions = [v for v in versions if v.status == status]

        if not versions:
            return None

        # Sort by version number
        def parse_version(v):
            parts = v.version.split(".")
            return tuple(int(p) for p in parts)

        versions.sort(key=parse_version, reverse=True)
        return versions[0]

    def parse_version_from_request(self, path: str = None, headers: dict = None, query_params: dict = None) -> str:
        """
        Parse API version from request.

        Args:
            path: Request path
            headers: Request headers
            query_params: Query parameters

        Returns:
            Version string
        """
        version = self.default_version

        if self.strategy == "url" and path:
            # Extract version from URL path: /v1/users -> 1
            match = re.match(r"/v(\d+(?:\.\d+)?)/", path)
            if match:
                version = match.group(1)
                if "." not in version:
                    version = f"{version}.0"

        elif self.strategy == "header" and headers:
            # Get version from header
            version = headers.get("X-API-Version", version)

        elif self.strategy == "query" and query_params:
            # Get version from query parameter
            version = query_params.get("version", version)

        elif self.strategy == "content_type" and headers:
            # Parse version from Accept header
            accept = headers.get("Accept", "")
            match = re.search(r"version=(\d+(?:\.\d+)?)", accept)
            if match:
                version = match.group(1)

        return version

    def is_version_supported(self, version: str) -> bool:
        """Check if a version is supported."""
        if version in self._versions:
            return self._versions[version].status != VersionStatus.SUNSET
        return False

    def is_version_deprecated(self, version: str) -> bool:
        """Check if a version is deprecated."""
        if version in self._versions:
            return self._versions[version].status == VersionStatus.DEPRECATED
        return False

    def get_deprecation_warning(self, version: str) -> dict | None:
        """Get deprecation warning for a version."""
        api_version = self._versions.get(version)
        if not api_version or api_version.status != VersionStatus.DEPRECATED:
            return None

        latest = self.get_latest_version(VersionStatus.STABLE)

        return {
            "deprecated": True,
            "sunset_date": api_version.sunset_date,
            "upgrade_to": latest.version if latest else None,
            "message": f"API version {version} is deprecated and will be sunset on {api_version.sunset_date}",
        }

    def get_version_headers(self, version: str) -> dict[str, str]:
        """Get headers to include in response for version info."""
        api_version = self._versions.get(version)
        if not api_version:
            return {}

        headers = {"X-API-Version": version, "X-API-Status": api_version.status.value}

        if api_version.status == VersionStatus.DEPRECATED:
            headers["Deprecation"] = "true"
            if api_version.sunset_date:
                headers["Sunset"] = api_version.sunset_date

            latest = self.get_latest_version(VersionStatus.STABLE)
            if latest:
                headers["Link"] = f'</v{latest.version}/>; rel="successor-version"'

        return headers

    def get_all_versions(self) -> list[dict]:
        """Get all registered versions."""
        return [
            {
                "version": v.version,
                "status": v.status.value,
                "release_date": v.release_date,
                "sunset_date": v.sunset_date,
                "changelog": v.changelog,
                "breaking_changes": v.breaking_changes if v.breaking_changes else None,
            }
            for v in sorted(
                self._versions.values(), key=lambda x: tuple(int(p) for p in x.version.split(".")), reverse=True
            )
        ]

    async def deprecate_version(self, version: str, sunset_date: str, migration_guide: str = None):
        """
        Mark a version as deprecated.

        Args:
            version: Version to deprecate
            sunset_date: Date when version will be removed
            migration_guide: Guide for migrating to newer version
        """
        if version not in self._versions:
            logger.warning(f"Cannot deprecate unknown version: {version}")
            return

        api_version = self._versions[version]
        api_version.status = VersionStatus.DEPRECATED
        api_version.deprecation_date = datetime.utcnow().isoformat()
        api_version.sunset_date = sunset_date

        if migration_guide:
            api_version.changelog.append(f"Migration guide: {migration_guide}")

        logger.warning(f"API version {version} deprecated, sunset on {sunset_date}")

    async def sunset_version(self, version: str):
        """
        Mark a version as sunset (no longer supported).

        Args:
            version: Version to sunset
        """
        if version not in self._versions:
            return

        self._versions[version].status = VersionStatus.SUNSET
        logger.info(f"API version {version} sunset")

    def get_handler(self, version: str, endpoint: str) -> Callable | None:
        """Get handler for versioned endpoint."""
        key = f"{version}:{endpoint}"
        return self._version_handlers.get(key)

    async def migrate_request(self, request_data: dict, from_version: str, to_version: str) -> dict:
        """
        Migrate request data between versions.

        Args:
            request_data: Original request data
            from_version: Source version
            to_version: Target version

        Returns:
            Migrated request data
        """
        if from_version == to_version:
            return request_data

        key = f"{from_version}->{to_version}"
        handler = self._migration_handlers.get(key)

        if handler:
            if asyncio.iscoroutinefunction(handler):
                return await handler(request_data)
            return handler(request_data)

        # No migration handler, return original
        return request_data


import asyncio  # noqa: E402

# Global instance
api_versioning_service = APIVersioningService(
    default_version=os.getenv("API_DEFAULT_VERSION", "1.0"), strategy=os.getenv("API_VERSION_STRATEGY", "url")
)
