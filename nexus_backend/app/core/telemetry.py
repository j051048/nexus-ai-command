"""OpenTelemetry setup for distributed tracing."""

import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


def setup_telemetry(app):
    """Initialize OpenTelemetry tracing for the FastAPI application.

    Conditionally enables tracing based on OTEL_ENABLED config.
    Gracefully degrades if opentelemetry packages are not installed.
    """
    otel_enabled = getattr(settings, "OTEL_ENABLED", False)
    if not settings.IS_PRODUCTION and not otel_enabled:
        logger.info("Telemetry disabled (non-production or OTEL_ENABLED not set)")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        resource = Resource.create({
            "service.name": "nexus-backend",
            "service.version": settings.VERSION,
            "deployment.environment": settings.ENV,
        })

        provider = TracerProvider(resource=resource)

        # Add OTLP exporter if endpoint configured
        otlp_endpoint = getattr(settings, "OTEL_EXPORTER_ENDPOINT", "")
        if otlp_endpoint:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        logger.info("OpenTelemetry tracing initialized")

    except ImportError:
        logger.warning("OpenTelemetry packages not installed, tracing disabled")
    except Exception as e:
        logger.warning(f"Telemetry setup failed: {e}")
