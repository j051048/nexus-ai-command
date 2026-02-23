"""OpenTelemetry setup for distributed tracing and metrics."""

import logging
import time

from app.core.config import settings

logger = logging.getLogger(__name__)


def setup_telemetry(app):
    """Initialize OpenTelemetry tracing and metrics for the FastAPI application.

    Conditionally enables tracing based on OTEL_ENABLED config.
    Gracefully degrades if opentelemetry packages are not installed.
    """
    otel_enabled = getattr(settings, "OTEL_ENABLED", False)
    if not settings.IS_PRODUCTION and not otel_enabled:
        logger.info("Telemetry disabled (non-production or OTEL_ENABLED not set)")
        return

    try:
        from opentelemetry import metrics, trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create(
            {
                "service.name": "nexus-backend",
                "service.version": settings.VERSION,
                "deployment.environment": settings.ENV,
            }
        )

        # Tracing
        provider = TracerProvider(resource=resource)

        otlp_endpoint = getattr(settings, "OTEL_EXPORTER_ENDPOINT", "")
        if otlp_endpoint:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)

        # Metrics
        meter_provider = MeterProvider(resource=resource)
        metrics.set_meter_provider(meter_provider)
        meter = metrics.get_meter("nexus-backend")

        request_counter = meter.create_counter(
            "http.server.request_count",
            description="Total HTTP requests",
        )
        request_duration = meter.create_histogram(
            "http.server.duration",
            description="HTTP request duration in milliseconds",
            unit="ms",
        )

        # Add metrics middleware
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.requests import Request

        class MetricsMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                start = time.perf_counter()
                response = await call_next(request)
                duration_ms = (time.perf_counter() - start) * 1000
                attrs = {
                    "http.method": request.method,
                    "http.route": request.url.path,
                    "http.status_code": response.status_code,
                }
                request_counter.add(1, attrs)
                request_duration.record(duration_ms, attrs)
                return response

        app.add_middleware(MetricsMiddleware)

        FastAPIInstrumentor.instrument_app(app)
        logger.info("OpenTelemetry tracing and metrics initialized")

    except ImportError:
        logger.warning("OpenTelemetry packages not installed, tracing disabled")
    except Exception as e:
        logger.warning(f"Telemetry setup failed: {e}")
