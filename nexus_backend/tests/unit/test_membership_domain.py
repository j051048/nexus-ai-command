from datetime import UTC, datetime, timedelta

from app.domains.admin_trust.membership import access_state, parse_datetime


def test_parse_datetime_normalizes_naive_values_to_utc() -> None:
    parsed = parse_datetime("2030-01-02T03:04:05")
    assert parsed is not None
    assert parsed.tzinfo == UTC


def test_access_state_prioritizes_expiry_over_active_status() -> None:
    now = datetime(2030, 1, 1, tzinfo=UTC)
    assert (
        access_state(
            {
                "plan": "enterprise",
                "status": "active",
                "current_period_end": (now - timedelta(seconds=1)).isoformat(),
            },
            now=now,
        )
        == "expired"
    )


def test_access_state_distinguishes_free_suspended_and_active() -> None:
    now = datetime(2030, 1, 1, tzinfo=UTC)
    assert access_state({"plan": "free", "status": "active"}, now=now) == "free"
    assert (
        access_state({"plan": "enterprise", "status": "suspended"}, now=now)
        == "suspended"
    )
    assert access_state({"plan": "enterprise", "status": "active"}, now=now) == "active"
