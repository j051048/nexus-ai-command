"""OpenTelemetry setup for distributed tracing and metrics."""

import logging

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

        # Note: Manual HTTP metrics middleware removed — FastAPIInstrumentor
        # below already collects http.server.request_count and http.server.duration.
        # Keeping a separate manual middleware would double-count all HTTP metrics.

        FastAPIInstrumentor.instrument_app(app)
        logger.info("OpenTelemetry tracing and metrics initialized")

    except ImportError:
        logger.warning("OpenTelemetry packages not installed, tracing disabled")
    except Exception as e:
        logger.warning(f"Telemetry setup failed: {e}")
