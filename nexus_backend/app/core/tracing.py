"""
OpenTelemetry 端到端追踪

提供完整的请求链路追踪，从 API 入口到 LLM 调用
"""

import logging
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.core.config import settings

logger = logging.getLogger(__name__)

# 全局 tracer
_tracer: trace.Tracer | None = None


def init_tracing():
    """初始化 OpenTelemetry"""
    global _tracer

    if _tracer is not None:
        return _tracer

    # 创建 Resource
    resource = Resource.create(
        {"service.name": "nexus-agent", "service.version": "1.0.0"}
    )

    # 创建 TracerProvider
    provider = TracerProvider(resource=resource)

    # 添加导出器
    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        # 生产环境：导出到 OTLP
        otlp_exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    else:
        # 开发环境：输出到控制台
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(__name__)

    logger.info("OpenTelemetry tracing initialized")
    return _tracer


def get_tracer() -> trace.Tracer:
    """获取 tracer"""
    if _tracer is None:
        return init_tracing()
    return _tracer


@contextmanager
def trace_span(name: str, attributes: dict = None):
    """创建 trace span 上下文管理器"""
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span
