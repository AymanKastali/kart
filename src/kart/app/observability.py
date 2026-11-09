"""Observability: JSON logs, OpenTelemetry traces and Sentry errors (overview.md).

Each process calls `set_up_observability` once, as it starts.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import sentry_sdk
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.urllib import URLLibInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

if TYPE_CHECKING:
    from kart.app.settings import Settings


def set_up_observability(process: str, settings: Settings) -> None:
    """Log JSON to stdout, trace as `kart-<process>`, and report errors to Sentry if set."""
    _log_json_lines()
    _start_tracing(f"kart-{process}", settings.otlp_endpoint)
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn)


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line, with the trace and span ids while a span is active."""

    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, str] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            line["trace_id"] = trace.format_trace_id(span_context.trace_id)
            line["span_id"] = trace.format_span_id(span_context.span_id)
        if record.exc_info:
            line["exception"] = self.formatException(record.exc_info)
        return json.dumps(line)


def _log_json_lines() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


def _start_tracing(service: str, otlp_endpoint: str | None) -> None:
    """Trace incoming and outgoing HTTP and every SQL statement, exporting over OTLP if set.

    Database engines must be created after this, because it instruments `create_engine`.
    """
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service}))
    if otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    # It declares support only below SQLAlchemy 2.1, but traces 2.1's statements correctly.
    SQLAlchemyInstrumentor().instrument(skip_dep_check=True)
    URLLibInstrumentor().instrument()
