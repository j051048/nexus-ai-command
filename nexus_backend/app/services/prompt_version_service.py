"""
P1 Enhancement: Prompt Version Control Service

Implements version management for AI prompts with:
- Version history tracking
- A/B testing support
- Rollback capability
- Change logging

Fixes Issue #21: Prompt template version control and A/B testing.
"""

import os
import json
import logging
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class PromptStatus(Enum):
    """Status of a prompt version."""
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass
class PromptVersion:
    """A single version of a prompt template."""
    version_id: str
    prompt_key: str
    content: str
    version_number: int
    status: PromptStatus
    created_by: str
    created_at: datetime
    updated_at: datetime
    change_description: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    ab_test_group: Optional[str] = None
    ab_test_weight: float = 1.0

    def to_dict(self) -> Dict:
        return {
            "version_id": self.version_id,
            "prompt_key": self.prompt_key,
            "content": self.content,
            "version_number": self.version_number,
            "status": self.status.value,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "change_description": self.change_description,
            "tags": self.tags,
            "metadata": self.metadata,
            "ab_test_group": self.ab_test_group,
            "ab_test_weight": self.ab_test_weight,
        }


@dataclass
class ABTestConfig:
    """A/B test configuration for prompts."""
    test_id: str
    prompt_key: str
    variants: Dict[str, float]  # version_id -> weight
    start_time: datetime
    end_time: Optional[datetime]
    created_by: str
    metrics: Dict[str, Any] = field(default_factory=dict)


class PromptVersionService:
    """
    P1 Enhancement: Prompt version control and A/B testing.
    
    Features:
    - Version history with diff tracking
    - A/B testing with weighted distribution
    - Rollback to previous versions
    - Change audit log
    - Hot-reload support
    """

    def __init__(self):
        self._versions: Dict[str, List[PromptVersion]] = {}  # prompt_key -> versions
        self._active_versions: Dict[str, str] = {}  # prompt_key -> active version_id
        self._ab_tests: Dict[str, ABTestConfig] = {}
        self._version_cache: Dict[str, PromptVersion] = {}  # version_id -> version
        self._change_log: List[Dict] = []
        
    def create_version(
        self,
        prompt_key: str,
        content: str,
        created_by: str,
        change_description: str = "",
        tags: List[str] = None,
        metadata: Dict = None,
        status: PromptStatus = PromptStatus.DRAFT
    ) -> PromptVersion:
        """Create a new version of a prompt."""
        # Get next version number
        existing = self._versions.get(prompt_key, [])
        next_version = max([v.version_number for v in existing], default=0) + 1
        
        # Generate version ID
        version_id = hashlib.md5(
            f"{prompt_key}:{next_version}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        version = PromptVersion(
            version_id=version_id,
            prompt_key=prompt_key,
            content=content,
            version_number=next_version,
            status=status,
            created_by=created_by,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            change_description=change_description,
            tags=tags or [],
            metadata=metadata or {}
        )
        
        # Store
        if prompt_key not in self._versions:
            self._versions[prompt_key] = []
        self._versions[prompt_key].append(version)
        self._version_cache[version_id] = version
        
        # Log change
        self._log_change("create", version, created_by)
        
        logger.info(f"Created prompt version: {prompt_key} v{next_version} ({version_id})")
        return version

    def activate_version(self, version_id: str, activated_by: str) -> Optional[PromptVersion]:
        """Activate a specific version of a prompt."""
        version = self._version_cache.get(version_id)
        if not version:
            logger.warning(f"Version not found: {version_id}")
            return None
        
        # Deactivate current active version
        prompt_key = version.prompt_key
        if prompt_key in self._active_versions:
            old_active_id = self._active_versions[prompt_key]
            old_version = self._version_cache.get(old_active_id)
            if old_version:
                old_version.status = PromptStatus.DEPRECATED
        
        # Activate new version
        version.status = PromptStatus.ACTIVE
        self._active_versions[prompt_key] = version_id
        
        # Log change
        self._log_change("activate", version, activated_by)
        
        logger.info(f"Activated prompt version: {prompt_key} v{version.version_number}")
        return version

    def rollback(self, prompt_key: str, rollback_by: str) -> Optional[PromptVersion]:
        """Rollback to previous version."""
        versions = self._versions.get(prompt_key, [])
        if len(versions) < 2:
            logger.warning(f"Cannot rollback: not enough versions for {prompt_key}")
            return None
        
        # Find the previous active version
        sorted_versions = sorted(versions, key=lambda v: v.version_number, reverse=True)
        for v in sorted_versions[1:]:  # Skip current
            if v.status in (PromptStatus.DEPRECATED, PromptStatus.ACTIVE):
                return self.activate_version(v.version_id, rollback_by)
        
        return None

    def get_active_version(self, prompt_key: str) -> Optional[PromptVersion]:
        """Get the currently active version of a prompt."""
        version_id = self._active_versions.get(prompt_key)
        if version_id:
            return self._version_cache.get(version_id)
        return None

    def get_version(self, version_id: str) -> Optional[PromptVersion]:
        """Get a specific version by ID."""
        return self._version_cache.get(version_id)

    def get_version_history(self, prompt_key: str, limit: int = 10) -> List[PromptVersion]:
        """Get version history for a prompt."""
        versions = self._versions.get(prompt_key, [])
        return sorted(versions, key=lambda v: v.version_number, reverse=True)[:limit]

    def create_ab_test(
        self,
        prompt_key: str,
        variants: Dict[str, float],
        created_by: str,
        duration_hours: int = 24 * 7
    ) -> ABTestConfig:
        """Create an A/B test for prompt variants."""
        test_id = hashlib.md5(
            f"{prompt_key}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        # Normalize weights
        total_weight = sum(variants.values())
        normalized = {k: v / total_weight for k, v in variants.items()}
        
        ab_test = ABTestConfig(
            test_id=test_id,
            prompt_key=prompt_key,
            variants=normalized,
            start_time=datetime.now(),
            end_time=datetime.now() + __import__("datetime").timedelta(hours=duration_hours),
            created_by=created_by
        )
        
        self._ab_tests[test_id] = ab_test
        
        # Mark versions as part of A/B test
        for version_id in variants:
            version = self._version_cache.get(version_id)
            if version:
                version.ab_test_group = test_id
                version.ab_test_weight = normalized[version_id]
        
        logger.info(f"Created A/B test: {test_id} for {prompt_key}")
        return ab_test

    def get_ab_test_variant(self, prompt_key: str, user_id: str) -> Optional[PromptVersion]:
        """Get the appropriate variant for a user based on A/B test."""
        # Find active A/B test for this prompt
        active_tests = [
            t for t in self._ab_tests.values()
            if t.prompt_key == prompt_key
            and t.end_time and t.end_time > datetime.now()
        ]
        
        if not active_tests:
            return self.get_active_version(prompt_key)
        
        # Use deterministic assignment based on user_id
        test = active_tests[0]
        user_hash = int(hashlib.md5(f"{test.test_id}:{user_id}".encode()).hexdigest()[:8], 16)
        selection = (user_hash % 10000) / 10000
        
        # Select variant
        cumulative = 0.0
        selected_version_id = None
        for version_id, weight in test.variants.items():
            cumulative += weight
            if selection <= cumulative:
                selected_version_id = version_id
                break
        
        if selected_version_id:
            return self._version_cache.get(selected_version_id)
        return self.get_active_version(prompt_key)

    def record_ab_test_metric(
        self,
        test_id: str,
        version_id: str,
        metric_name: str,
        value: float
    ):
        """Record a metric for A/B test analysis."""
        test = self._ab_tests.get(test_id)
        if not test:
            return
        
        if "metrics" not in test.metrics:
            test.metrics["metrics"] = {}
        if version_id not in test.metrics["metrics"]:
            test.metrics["metrics"][version_id] = {}
        if metric_name not in test.metrics["metrics"][version_id]:
            test.metrics["metrics"][version_id][metric_name] = []
        
        test.metrics["metrics"][version_id][metric_name].append({
            "value": value,
            "timestamp": datetime.now().isoformat()
        })

    def get_ab_test_results(self, test_id: str) -> Dict:
        """Get A/B test results summary."""
        test = self._ab_tests.get(test_id)
        if not test:
            return {"error": "Test not found"}
        
        return {
            "test_id": test_id,
            "prompt_key": test.prompt_key,
            "variants": test.variants,
            "start_time": test.start_time.isoformat(),
            "end_time": test.end_time.isoformat() if test.end_time else None,
            "metrics": test.metrics.get("metrics", {})
        }

    def _log_change(self, action: str, version: PromptVersion, actor: str):
        """Log a prompt change for audit."""
        self._change_log.append({
            "action": action,
            "prompt_key": version.prompt_key,
            "version_id": version.version_id,
            "version_number": version.version_number,
            "actor": actor,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep log manageable
        if len(self._change_log) > 1000:
            self._change_log = self._change_log[-500:]

    def get_change_log(self, prompt_key: str = None, limit: int = 100) -> List[Dict]:
        """Get change log for audit."""
        log = self._change_log
        if prompt_key:
            log = [l for l in log if l["prompt_key"] == prompt_key]
        return log[-limit:]

    async def record_response_metrics(
        self,
        prompt_key: str,
        user_id: str,
        response_time_ms: int,
        token_count: int,
        user_rating: Optional[float] = None,
        db=None,
    ):
        """
        #24 Prompt Performance Analysis: Record response quality metrics
        for the active prompt version or A/B test variant.
        """
        # Determine which version was used
        variant = self.get_ab_test_variant(prompt_key, user_id)
        version_id = variant.version_id if variant else self._active_versions.get(prompt_key)

        if not version_id:
            return

        # Record to A/B test if applicable
        if variant and variant.ab_test_group:
            self.record_ab_test_metric(variant.ab_test_group, version_id, "response_time_ms", response_time_ms)
            self.record_ab_test_metric(variant.ab_test_group, version_id, "token_count", token_count)
            if user_rating is not None:
                self.record_ab_test_metric(variant.ab_test_group, version_id, "user_rating", user_rating)

        # Persist to DB
        if db:
            try:
                await db.table("prompt_metrics").insert({
                    "prompt_key": prompt_key,
                    "version_id": version_id,
                    "user_id": user_id,
                    "response_time_ms": response_time_ms,
                    "token_count": token_count,
                    "user_rating": user_rating,
                }).execute()
            except Exception as e:
                logger.debug(f"Failed to persist prompt metrics: {e}")

    async def persist_to_db(self, db=None):
        """Persist prompt versions to database."""
        if not db:
            return
        
        try:
            for prompt_key, versions in self._versions.items():
                for version in versions:
                    await db.table("prompt_versions").upsert({
                        "version_id": version.version_id,
                        "prompt_key": version.prompt_key,
                        "content": version.content,
                        "version_number": version.version_number,
                        "status": version.status.value,
                        "created_by": version.created_by,
                        "change_description": version.change_description,
                        "tags": version.tags,
                        "metadata": version.metadata
                    }).execute()
        except Exception as e:
            logger.error(f"Failed to persist prompt versions: {e}")

    async def load_from_db(self, db=None):
        """Load prompt versions from database."""
        if not db:
            return
        
        try:
            res = await db.table("prompt_versions").select("*").execute()
            for row in res.data or []:
                version = PromptVersion(
                    version_id=row["version_id"],
                    prompt_key=row["prompt_key"],
                    content=row["content"],
                    version_number=row["version_number"],
                    status=PromptStatus(row["status"]),
                    created_by=row["created_by"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    change_description=row.get("change_description", ""),
                    tags=row.get("tags", []),
                    metadata=row.get("metadata", {})
                )
                
                if version.prompt_key not in self._versions:
                    self._versions[version.prompt_key] = []
                self._versions[version.prompt_key].append(version)
                self._version_cache[version.version_id] = version
                
                if version.status == PromptStatus.ACTIVE:
                    self._active_versions[version.prompt_key] = version.version_id
            
            logger.info(f"Loaded {len(self._version_cache)} prompt versions from database")
        except Exception as e:
            logger.error(f"Failed to load prompt versions: {e}")


# Global instance
prompt_version_service = PromptVersionService()
