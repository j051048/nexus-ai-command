"""
Item 44: Prometheus /metrics Endpoint

Provides Prometheus-compatible metrics using prometheus_client library.
Falls back to a simple hand-rolled implementation if the library is absent.

Exposed metrics:
  - http_requests_total (counter, labels: method, path, status)
  - http_request_duration_seconds (histogram, labels: method, path)
  - llm_requests_total (counter, labels: model, status)
  - llm_request_duration_seconds (histogram, labels: model)
  - active_websocket_connections (gauge)
  - agent_executions_total (counter, labels: complexity, status)
"""

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try prometheus_client; fall back to lightweight in-memory implementation
# ---------------------------------------------------------------------------

_prom_available = False

try:
    from prometheus_client import (
        REGISTRY,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    HTTP_REQUESTS_TOTAL = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
    )
    HTTP_REQUEST_DURATION = Histogram(
        "http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "path"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    )
    LLM_REQUESTS_TOTAL = Counter(
        "llm_requests_total",
        "Total LLM API requests",
        ["model", "status"],
    )
    LLM_REQUEST_DURATION = Histogram(
        "llm_request_duration_seconds",
        "LLM request duration in seconds",
        ["model"],
        buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
    )
    ACTIVE_WS_CONNECTIONS = Gauge(
        "active_websocket_connections",
        "Number of active WebSocket connections",
    )
    AGENT_EXECUTIONS_TOTAL = Counter(
        "agent_executions_total",
        "Total agent executions",
        ["complexity", "status"],
    )

    _prom_available = True
    logger.info("[Metrics] prometheus_client initialized")

except ImportError:
    logger.info("[Metrics] prometheus_client not installed, using in-memory fallback")

# ---------------------------------------------------------------------------
# In-memory fallback (lightweight, no external dep)
# ---------------------------------------------------------------------------

_mem_counters: dict[str, float] = defaultdict(float)
_mem_histograms: dict[str, list[float]] = defaultdict(list)
_mem_gauges: dict[str, float] = defaultdict(float)

# Max samples per histogram bucket (prevent unbounded memory)
_MAX_HISTOGRAM_SAMPLES = 5000


# ---------------------------------------------------------------------------
# Public API — always safe to call
# ---------------------------------------------------------------------------


def observe_http_request(
    method: str, path: str, status: int, duration_s: float
) -> None:
    """Record an HTTP request metric."""
    # Normalize path: collapse IDs to reduce cardinality
    normalized = _normalize_path(path)

    if _prom_available:
        HTTP_REQUESTS_TOTAL.labels(
            method=method, path=normalized, status=str(status)
        ).inc()
        HTTP_REQUEST_DURATION.labels(method=method, path=normalized).observe(duration_s)
    else:
        _mem_counters[f"http_requests_total|{method}|{normalized}|{status}"] += 1
        _hist_add(f"http_request_duration_seconds|{method}|{normalized}", duration_s)


# ---------------------------------------------------------------------------
# Metrics endpoint content generation
# ---------------------------------------------------------------------------


def generate_metrics_text() -> str:
    """
    Generate Prometheus-format metrics text.
    Uses prometheus_client when available, otherwise hand-rolls the output.
    """
    if _prom_available:
        return generate_latest(REGISTRY).decode("utf-8")

    # Fallback: hand-rolled Prometheus exposition format
    lines: list[str] = []

    # Counters
    for key, value in sorted(_mem_counters.items()):
        parts = key.split("|")
        metric_name = parts[0]
        labels = parts[1:] if len(parts) > 1 else []
        label_str = _format_labels(metric_name, labels)
        lines.append(f"{metric_name}{label_str} {value}")

    # Gauges
    for key, value in sorted(_mem_gauges.items()):
        lines.append(f"{key} {value}")

    # Histograms (simplified: just sum and count)
    seen_hists: set[str] = set()
    for key, samples in sorted(_mem_histograms.items()):
        parts = key.split("|")
        metric_name = parts[0]
        if metric_name in seen_hists:
            continue
        seen_hists.add(metric_name)
        labels = parts[1:] if len(parts) > 1 else []
        label_str = _format_labels(metric_name, labels)
        total = sum(samples)
        count = len(samples)
        lines.append(f"{metric_name}_sum{label_str} {total:.6f}")
        lines.append(f"{metric_name}_count{label_str} {count}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalize_path(path: str) -> str:
    """Collapse UUIDs and numeric IDs in path to reduce label cardinality."""
    import re

    # Replace UUIDs
    path = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "{id}",
        path,
    )
    # Replace numeric IDs in path segments
    path = re.sub(r"/\d+(?=/|$)", "/{id}", path)
    return path


def _format_labels(metric_name: str, label_values: list[str]) -> str:
    """Format label values for Prometheus exposition."""
    if not label_values:
        return ""
    label_map = {
        "http_requests_total": ["method", "path", "status"],
        "http_request_duration_seconds": ["method", "path"],
        "llm_requests_total": ["model", "status"],
        "llm_request_duration_seconds": ["model"],
        "agent_executions_total": ["complexity", "status"],
    }
    names = label_map.get(metric_name, [f"l{i}" for i in range(len(label_values))])
    pairs = [f'{n}="{v}"' for n, v in zip(names, label_values, strict=False)]
    return "{" + ",".join(pairs) + "}"


def _hist_add(key: str, value: float) -> None:
    """Add a sample to an in-memory histogram with size cap."""
    samples = _mem_histograms[key]
    if len(samples) >= _MAX_HISTOGRAM_SAMPLES:
        # Drop oldest half to prevent unbounded growth
        _mem_histograms[key] = samples[_MAX_HISTOGRAM_SAMPLES // 2 :]
    _mem_histograms[key].append(value)
