"""Ops alerting settings.

Keeps ``app/core/config.py`` a wiring point instead of a growing file, while
preserving the flat ``UPPER_CASE`` env-var contract.
"""

from pydantic import BaseModel, Field, field_validator

#: Webhook payload shapes the dispatcher knows how to build.
ALERT_WEBHOOK_FORMATS = ("generic", "slack", "feishu")


class AlertSettings(BaseModel):
    """Delivery and thresholds for SLO alerting."""

    ALERTING_ENABLED: bool = Field(default=True)
    ALERT_WEBHOOK_URL: str = Field(default="")
    ALERT_WEBHOOK_FORMAT: str = Field(default="generic")
    ALERT_WEBHOOK_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0, le=60)
    #: Minimum gap before the same alert key is sent again.
    ALERT_MIN_INTERVAL_SECONDS: int = Field(default=1800, ge=60)
    #: Alerting never blocks the beat worker for longer than this.
    ALERT_MAX_EVENTS_PER_RUN: int = Field(default=25, ge=1, le=200)

    ALERT_AGENT_SUCCESS_RATE_THRESHOLD: float = Field(default=0.90, gt=0, le=1)
    ALERT_AGENT_MIN_SAMPLES: int = Field(default=10, ge=1)
    ALERT_BACKUP_FAILURE_LOOKBACK_HOURS: int = Field(default=24, ge=1, le=720)
    ALERT_RETENTION_FAILURE_LOOKBACK_HOURS: int = Field(default=48, ge=1, le=720)
    #: How many organizations the quality-SLO rule inspects per run.
    ALERT_ORG_SAMPLE_LIMIT: int = Field(default=25, ge=1, le=200)

    @field_validator("ALERT_WEBHOOK_FORMAT")
    @classmethod
    def _validate_format(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in ALERT_WEBHOOK_FORMATS:
            expected = ", ".join(ALERT_WEBHOOK_FORMATS)
            raise ValueError(
                f"ALERT_WEBHOOK_FORMAT must be one of {expected}; got {value!r}"
            )
        return normalized
