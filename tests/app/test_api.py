from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
from opentelemetry.trace import SpanKind

from kart.app.api import app
from tests.conftest import the_one_span

if TYPE_CHECKING:
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

client = TestClient(app)


def test_health_answers_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_describes_the_health_route() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]


def test_a_request_is_traced(spans: InMemorySpanExporter) -> None:
    client.get("/v1/storefront/nothing-here")

    server_span = the_one_span(spans, SpanKind.SERVER)
    assert server_span.attributes is not None
    assert server_span.attributes["http.response.status_code"] == 404


def test_health_checks_are_not_traced(spans: InMemorySpanExporter) -> None:
    client.get("/health")

    assert spans.get_finished_spans() == ()
