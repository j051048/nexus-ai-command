"""Tests for public metrics ingestion hardening."""

import pytest
from pydantic import ValidationError

from app.routers.metrics import WebVitalPayload


def test_web_vital_payload_normalizes_metric_labels():
    payload = WebVitalPayload(
        name="lcp",
        value=123.4,
        rating="GOOD",
        path="/customers/123?debug=true#section",
    )

    assert payload.name == "LCP"
    assert payload.rating == "good"
    assert payload.path == "/customers/123"


@pytest.mark.parametrize(
    ("raw_rating", "expected"),
    [
        (None, "unknown"),
        ("needsImprovement", "needs-improvement"),
        ("needs_improvement", "needs-improvement"),
        ("needs improvement", "needs-improvement"),
    ],
)
def test_web_vital_payload_accepts_browser_rating_variants(raw_rating, expected):
    payload = WebVitalPayload(name="CLS", value=1, rating=raw_rating, path="/")

    assert payload.rating == expected


@pytest.mark.parametrize("name", ["custom_metric", "request_count", ""])
def test_web_vital_payload_rejects_unknown_metric_names(name: str):
    with pytest.raises(ValidationError):
        WebVitalPayload(name=name, value=1, rating="good", path="/")


@pytest.mark.parametrize("rating", ["great", "bad", "ok"])
def test_web_vital_payload_rejects_unknown_ratings(rating: str):
    with pytest.raises(ValidationError):
        WebVitalPayload(name="CLS", value=1, rating=rating, path="/")
