from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagate import inject
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from app.core.config import Settings


_provider_configured = False
_fastapi_instrumented = False
_sqlalchemy_instrumented = False
_celery_instrumented = False


def configure_tracing(
    settings: Settings,
    *,
    app: Any | None = None,
    sqlalchemy_engine: Any | None = None,
    celery_app: Any | None = None,
) -> None:
    global _provider_configured, _fastapi_instrumented, _sqlalchemy_instrumented, _celery_instrumented

    if not settings.tracing_enabled:
        return

    if not _provider_configured:
        resource = Resource.create(
            {"service.name": settings.otel_service_name})
        tracer_provider = TracerProvider(resource=resource)
        span_exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
        trace.set_tracer_provider(tracer_provider)
        _provider_configured = True

    if app is not None and not _fastapi_instrumented:
        FastAPIInstrumentor.instrument_app(app)
        _fastapi_instrumented = True

    if sqlalchemy_engine is not None and not _sqlalchemy_instrumented:
        SQLAlchemyInstrumentor().instrument(engine=sqlalchemy_engine.sync_engine)
        _sqlalchemy_instrumented = True

    if celery_app is not None and not _celery_instrumented:
        CeleryInstrumentor().instrument()
        _celery_instrumented = True


def get_tracer(name: str):
    return trace.get_tracer(name)


def inject_trace_headers(headers: Mapping[str, str] | None = None) -> dict[str, str]:
    carrier = dict(headers or {})
    inject(carrier)
    return carrier


def extract_trace_context(headers: Mapping[str, str] | None = None):
    return TraceContextTextMapPropagator().extract(dict(headers or {}))


def get_current_trace_identifiers() -> tuple[str | None, str | None]:
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None, None
    return format(span_context.trace_id, "032x"), format(span_context.span_id, "016x")


@contextmanager
def start_trace_span(
    name: str,
    *,
    headers: Mapping[str, str] | None = None,
    attributes: Mapping[str, Any] | None = None,
):
    tracer = get_tracer(name)
    context = extract_trace_context(headers)
    with tracer.start_as_current_span(name, context=context) as span:
        for key, value in (attributes or {}).items():
            if value is not None:
                span.set_attribute(key, value)
        yield span


def build_event_context(*, correlation_id: str | None, user_id: str | None):
    from app.events.schemas import EventContext

    carrier = inject_trace_headers()
    trace_id, span_id = get_current_trace_identifiers()
    return EventContext(
        trace_id=trace_id,
        span_id=span_id,
        traceparent=carrier.get("traceparent"),
        tracestate=carrier.get("tracestate"),
        correlation_id=correlation_id,
        user_id=user_id,
    )
