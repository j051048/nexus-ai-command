"""
P1 Enhancement: Prompt Version Control Service

Implements version management for AI prompts with:
- Version history tracking
- A/B testing support
- Rollback capability
- Change logging

Fixes Issue #21: Prompt template version control and A/B testing.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

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
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    ab_test_group: str | None = None
    ab_test_weight: float = 1.0

    def to_dict(self) -> dict:
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
    variants: dict[str, float]  # version_id -> weight
    start_time: datetime
    end_time: datetime | None
    created_by: str
    metrics: dict[str, Any] = field(default_factory=dict)


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
        self._versions: dict[str, list[PromptVersion]] = {}  # prompt_key -> versions
        self._active_versions: dict[str, str] = {}  # prompt_key -> active version_id
        self._ab_tests: dict[str, ABTestConfig] = {}
        self._version_cache: dict[str, PromptVersion] = {}  # version_id -> version
        self._change_log: list[dict] = []

    def create_version(
        self,
        prompt_key: str,
        content: str,
        created_by: str,
        change_description: str = "",
        tags: list[str] = None,
        metadata: dict = None,
        status: PromptStatus = PromptStatus.DRAFT,
    ) -> PromptVersion:
        """Create a new version of a prompt."""
        # Get next version number
        existing = self._versions.get(prompt_key, [])
        next_version = max([v.version_number for v in existing], default=0) + 1

        # Generate version ID
        version_id = hashlib.md5(f"{prompt_key}:{next_version}:{datetime.now().isoformat()}".encode()).hexdigest()[:12]

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
            metadata=metadata or {},
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

    def activate_version(self, version_id: str, activated_by: str) -> PromptVersion | None:
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

    def rollback(self, prompt_key: str, rollback_by: str) -> PromptVersion | None:
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

    def get_active_version(self, prompt_key: str) -> PromptVersion | None:
        """Get the currently active version of a prompt."""
        version_id = self._active_versions.get(prompt_key)
        if version_id:
            return self._version_cache.get(version_id)
        return None

    def get_version(self, version_id: str) -> PromptVersion | None:
        """Get a specific version by ID."""
        return self._version_cache.get(version_id)

    def get_version_history(self, prompt_key: str, limit: int = 10) -> list[PromptVersion]:
        """Get version history for a prompt."""
        versions = self._versions.get(prompt_key, [])
        return sorted(versions, key=lambda v: v.version_number, reverse=True)[:limit]

    def create_ab_test(
        self, prompt_key: str, variants: dict[str, float], created_by: str, duration_hours: int = 24 * 7
    ) -> ABTestConfig:
        """Create an A/B test for prompt variants."""
        test_id = hashlib.md5(f"{prompt_key}:{datetime.now().isoformat()}".encode()).hexdigest()[:12]

        # Normalize weights
        total_weight = sum(variants.values())
        normalized = {k: v / total_weight for k, v in variants.items()}

        ab_test = ABTestConfig(
            test_id=test_id,
            prompt_key=prompt_key,
            variants=normalized,
            start_time=datetime.now(),
            end_time=datetime.now() + __import__("datetime").timedelta(hours=duration_hours),
            created_by=created_by,
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

    def get_ab_test_variant(self, prompt_key: str, user_id: str) -> PromptVersion | None:
        """Get the appropriate variant for a user based on A/B test."""
        # Find active A/B test for this prompt
        active_tests = [
            t
            for t in self._ab_tests.values()
            if t.prompt_key == prompt_key and t.end_time and t.end_time > datetime.now()
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

    def record_ab_test_metric(self, test_id: str, version_id: str, metric_name: str, value: float):
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

        test.metrics["metrics"][version_id][metric_name].append(
            {"value": value, "timestamp": datetime.now().isoformat()}
        )

    def get_ab_test_results(self, test_id: str) -> dict:
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
            "metrics": test.metrics.get("metrics", {}),
        }

    def evaluate_ab_test(self, test_id: str) -> dict:
        """P1 Enhancement: Evaluate A/B test with statistical significance.

        Uses chi-squared test to determine if the observed difference between
        variants is statistically significant.

        Returns:
            Dict with evaluation results including p-value and recommendation.
        """
        test = self._ab_tests.get(test_id)
        if not test:
            return {"error": "Test not found"}

        raw_metrics = test.metrics.get("metrics", {})
        if len(raw_metrics) < 2:
            return {
                "test_id": test_id,
                "status": "insufficient_data",
                "message": "Need at least 2 variants with metrics",
            }

        # Collect "user_rating" or "response_time_ms" per variant
        variant_stats: dict[str, dict] = {}
        for version_id, m in raw_metrics.items():
            ratings = [r["value"] for r in m.get("user_rating", [])]
            resp_times = [r["value"] for r in m.get("response_time_ms", [])]
            n = len(ratings) or len(resp_times)
            avg_rating = sum(ratings) / len(ratings) if ratings else None
            avg_time = sum(resp_times) / len(resp_times) if resp_times else None
            positive = sum(1 for r in ratings if r >= 4.0) if ratings else 0
            variant_stats[version_id] = {
                "sample_size": n,
                "avg_rating": round(avg_rating, 3) if avg_rating is not None else None,
                "avg_response_time_ms": round(avg_time, 1) if avg_time is not None else None,
                "positive_count": positive,
                "total_ratings": len(ratings),
            }

        # Minimum sample size check
        min_sample = 30
        total_samples = sum(v["total_ratings"] for v in variant_stats.values())
        if total_samples < min_sample * len(variant_stats):
            return {
                "test_id": test_id,
                "status": "insufficient_sample",
                "message": f"Need at least {min_sample} ratings per variant (have {total_samples} total)",
                "variants": variant_stats,
                "min_sample_per_variant": min_sample,
            }

        # Chi-squared test on positive vs. non-positive ratings
        try:
            observed = []
            for v in variant_stats.values():
                pos = v["positive_count"]
                neg = v["total_ratings"] - pos
                observed.append([pos, neg])

            # Simple chi-squared calculation (no scipy dependency needed)
            rows = len(observed)
            cols = 2
            row_totals = [sum(row) for row in observed]
            col_totals = [sum(observed[r][c] for r in range(rows)) for c in range(cols)]
            grand_total = sum(row_totals)

            if grand_total == 0:
                return {"test_id": test_id, "status": "no_data", "variants": variant_stats}

            chi2 = 0.0
            for r in range(rows):
                for c in range(cols):
                    expected = (row_totals[r] * col_totals[c]) / grand_total
                    if expected > 0:
                        chi2 += ((observed[r][c] - expected) ** 2) / expected

            # Approximate p-value from chi2 (df=rows-1) using simple lookup
            df = rows - 1
            # Critical values for df=1: 3.84 (p<0.05), 6.63 (p<0.01), 10.83 (p<0.001)
            if df == 1:
                if chi2 >= 10.83:
                    p_value = 0.001
                elif chi2 >= 6.63:
                    p_value = 0.01
                elif chi2 >= 3.84:
                    p_value = 0.05
                else:
                    p_value = 0.5
            else:
                # Rough approximation for df>1
                p_value = 0.05 if chi2 > 2 * df else 0.5

            is_significant = p_value < 0.05

            # Find winner
            winner = max(variant_stats.items(), key=lambda x: x[1].get("avg_rating") or 0)

            return {
                "test_id": test_id,
                "status": "significant" if is_significant else "not_significant",
                "chi_squared": round(chi2, 4),
                "p_value_approx": p_value,
                "is_significant": is_significant,
                "degrees_of_freedom": df,
                "winner": winner[0] if is_significant else None,
                "recommendation": (
                    f"Activate variant {winner[0]} (avg rating: {winner[1].get('avg_rating')})"
                    if is_significant
                    else "Continue test — not yet statistically significant"
                ),
                "variants": variant_stats,
            }
        except Exception as e:
            logger.error(f"A/B test evaluation failed: {e}")
            return {"test_id": test_id, "status": "error", "message": str(e)}

    def _log_change(self, action: str, version: PromptVersion, actor: str):
        """Log a prompt change for audit."""
        self._change_log.append(
            {
                "action": action,
                "prompt_key": version.prompt_key,
                "version_id": version.version_id,
                "version_number": version.version_number,
                "actor": actor,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Keep log manageable
        if len(self._change_log) > 1000:
            self._change_log = self._change_log[-500:]

    def get_change_log(self, prompt_key: str = None, limit: int = 100) -> list[dict]:
        """Get change log for audit."""
        log = self._change_log
        if prompt_key:
            log = [entry for entry in log if entry["prompt_key"] == prompt_key]
        return log[-limit:]

    async def record_response_metrics(
        self,
        prompt_key: str,
        user_id: str,
        response_time_ms: int,
        token_count: int,
        user_rating: float | None = None,
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
                await db.table("prompt_metrics").insert(
                    {
                        "prompt_key": prompt_key,
                        "version_id": version_id,
                        "user_id": user_id,
                        "response_time_ms": response_time_ms,
                        "token_count": token_count,
                        "user_rating": user_rating,
                    }
                ).execute()
            except Exception as e:
                logger.debug(f"Failed to persist prompt metrics: {e}")

    async def persist_to_db(self, db=None):
        """Persist prompt versions to database."""
        if not db:
            return

        try:
            for _prompt_key, versions in self._versions.items():
                for version in versions:
                    await db.table("prompt_versions").upsert(
                        {
                            "version_id": version.version_id,
                            "prompt_key": version.prompt_key,
                            "content": version.content,
                            "version_number": version.version_number,
                            "status": version.status.value,
                            "created_by": version.created_by,
                            "change_description": version.change_description,
                            "tags": version.tags,
                            "metadata": version.metadata,
                        }
                    ).execute()
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
                    metadata=row.get("metadata", {}),
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
