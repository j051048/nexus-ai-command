"""Backup and data-retention settings.

``app/core/config.py`` is a single wiring point under a source-size gate, so
new configuration sections live in their own mixin instead of growing that
file. ``Settings`` inherits this class, which keeps the flat ``UPPER_CASE``
env-var contract (``BACKUP_STORAGE_BACKEND=...``) unchanged.
"""

from pydantic import BaseModel, Field, field_validator

#: Backends a backup payload can be written to.
BACKUP_STORAGE_BACKENDS = ("database", "filesystem", "s3")


class BackupRetentionSettings(BaseModel):
    """Off-site backup storage and data-retention windows."""

    # ── Backup storage ────────────────────────────────────────────────────
    # "database" keeps the historical behaviour (payload inside
    # backup_records). "filesystem" and "s3" move the payload off the primary
    # database, which is what makes a restore possible after database loss.
    BACKUP_STORAGE_BACKEND: str = Field(default="database")
    BACKUP_STORAGE_PATH: str = Field(default="/var/lib/nexus/backups")
    BACKUP_S3_BUCKET: str = Field(default="")
    BACKUP_S3_PREFIX: str = Field(default="nexus-backups")
    BACKUP_S3_REGION: str = Field(default="us-east-1")
    BACKUP_S3_ENDPOINT_URL: str = Field(default="")
    BACKUP_S3_ACCESS_KEY_ID: str = Field(default="")
    BACKUP_S3_SECRET_ACCESS_KEY: str = Field(default="")

    # ── Backup lifecycle ──────────────────────────────────────────────────
    BACKUP_RETENTION_DAYS: int = Field(default=30, ge=1)
    BACKUP_SCHEDULE_BATCH_LIMIT: int = Field(default=10, ge=1)
    BACKUP_SCHEDULE_LEASE_SECONDS: int = Field(default=1800, ge=60)
    BACKUP_VERIFY_AFTER_WRITE: bool = Field(default=True)

    # ── Data retention enforcement ────────────────────────────────────────
    # Off by default: deleting customer data must be an explicit operator
    # decision. While off, /api/compliance/retention reports enforced=false.
    DATA_RETENTION_ENFORCEMENT_ENABLED: bool = Field(default=False)
    DATA_RETENTION_AUDIT_LOG_DAYS: int = Field(default=365, ge=1)
    DATA_RETENTION_CHAT_MESSAGE_DAYS: int = Field(default=90, ge=1)
    DATA_RETENTION_TOKEN_USAGE_DAYS: int = Field(default=180, ge=1)
    DATA_RETENTION_BATCH_SIZE: int = Field(default=500, ge=1, le=5000)

    @field_validator("BACKUP_STORAGE_BACKEND")
    @classmethod
    def _validate_backend(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in BACKUP_STORAGE_BACKENDS:
            expected = ", ".join(BACKUP_STORAGE_BACKENDS)
            raise ValueError(
                f"BACKUP_STORAGE_BACKEND must be one of {expected}; got {value!r}"
            )
        return normalized
