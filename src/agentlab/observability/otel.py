from __future__ import annotations

import json
import os
from typing import Sequence

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
except Exception:
    OTLPSpanExporter = None  # type: ignore


class JsonlFileSpanExporter(SpanExporter):
    """把 spans 以 JSONL（每行一个 JSON）写入文件，方便 grep / 之后做分析。"""

    def __init__(self, path: str) -> None:
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        with open(self.path, "a", encoding="utf-8") as f:
            for sp in spans:
                if sp.name.startswith("GET /session/{session_id}/events"):
                    continue
                ctx = sp.get_span_context()
                rec = {
                    "name": sp.name,
                    "trace_id": f"{ctx.trace_id:032x}",
                    "span_id": f"{ctx.span_id:016x}",
                    "parent_span_id": f"{sp.parent.span_id:016x}" if sp.parent else None,
                    "start_time_ns": sp.start_time,
                    "end_time_ns": sp.end_time,
                    "status": str(sp.status.status_code),
                    "attributes": dict(sp.attributes) if sp.attributes else {},
                    # events / links 如果你想要也可以加，但先保持简洁
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return


def setup_otel(service_name: str = "agentlab") -> None:
    """初始化 OpenTelemetry Tracing（默认写文件，可选 OTLP）。"""
    resource = Resource.create({"service.name": service_name})

    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    # ✅ 1) 默认：写到文件（替代 ConsoleSpanExporter，终端不再刷屏）
    provider.add_span_processor(
        BatchSpanProcessor(JsonlFileSpanExporter("logs/traces.jsonl"))
    )

    # ✅ 2) 可选：OTLP exporter（如果你配置了 OTEL_EXPORTER_OTLP_ENDPOINT）
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint and OTLPSpanExporter:
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        )
