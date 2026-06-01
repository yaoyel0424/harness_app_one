"""OpenTelemetry 追踪初始化。"""

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy.ext.asyncio import AsyncEngine

from myapp.config import Settings


def setup_telemetry(
    app: object,
    settings: Settings,
    engine: AsyncEngine | None = None,
) -> None:
    """配置 OTLP 导出与 FastAPI/SQLAlchemy 自动埋点。"""
    if not settings.otel_enabled:
        return

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    if engine is not None:
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
