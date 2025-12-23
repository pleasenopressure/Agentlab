from __future__ import annotations

import os
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
except Exception:
    OTLPSpanExporter = None  # type: ignore


def setup_otel(service_name: str = "agentlab") -> None:
    """初始化 OpenTelemetry Tracing（本地默认输出到控制台，可选 OTLP）。"""
    resource = Resource.create({"service.name": service_name})

    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    # 1) 默认：控制台 exporter（本地立刻可见）
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    # 2) 可选：OTLP exporter（如果你配置了 OTEL_EXPORTER_OTLP_ENDPOINT）
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint and OTLPSpanExporter:
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        )
