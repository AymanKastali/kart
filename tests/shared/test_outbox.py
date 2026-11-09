"""The outbox end to end: a context commits an event, Debezium Server captures it from the
write-ahead log, and RabbitMQ delivers it."""

import contextlib
import json
from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from opentelemetry import trace
from opentelemetry.trace import SpanKind
from sqlalchemy import Engine, text

from kart.app.database import unit_of_work
from kart.app.rabbitmq_setup import EVENTS_EXCHANGE
from kart.shared.kernel.event_envelope import EventEnvelope
from kart.shared.outbox import write_to_outbox
from tests.conftest import the_one_span
from tests.shared.conftest import an_event, eventually

if TYPE_CHECKING:
    from collections.abc import Mapping

    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from pika.adapters.blocking_connection import BlockingChannel
    from testcontainers.core.container import DockerContainer

# Events flow only while Debezium runs.
pytestmark = pytest.mark.usefixtures("debezium")


class Abandoned(Exception):  # noqa: N818 what happened, not an error
    """Raised inside a unit of work to roll it back."""


def commit(engine: Engine, event: EventEnvelope) -> None:
    with unit_of_work(engine, "throwaway") as session:
        write_to_outbox(session, event, aggregate_type="widget", aggregate_id=uuid4())


def roll_back(engine: Engine, event: EventEnvelope) -> None:
    with contextlib.suppress(Abandoned), unit_of_work(engine, "throwaway") as session:
        write_to_outbox(session, event, aggregate_type="widget", aggregate_id=uuid4())
        raise Abandoned


def queue_bound_to(channel: BlockingChannel, routing_key: str) -> str:
    queue = f"test.{uuid4().hex}"
    channel.queue_declare(queue, exclusive=True)
    channel.queue_bind(queue, EVENTS_EXCHANGE, routing_key)
    return queue


def next_message(channel: BlockingChannel, queue: str) -> tuple[Mapping[str | bytes, object], str]:
    """The headers and body of the next message on `queue`, waiting for it to arrive."""

    def get() -> tuple[Mapping[str | bytes, object], str] | None:
        method, properties, body = channel.basic_get(queue, auto_ack=True)
        if method is None or properties is None or body is None:
            return None
        return properties.headers or {}, body.decode()

    return eventually(get, f"A message on {queue}")


def test_a_committed_event_arrives_on_a_queue_bound_to_its_type(
    engine: Engine, channel: BlockingChannel
) -> None:
    queue = queue_bound_to(channel, "widget.made.v1")
    event = an_event("widget.made.v1")

    commit(engine, event)

    headers, body = next_message(channel, queue)
    # Debezium writes header values as JSON.
    assert UUID(json.loads(str(headers["id"]))) == event.event_id
    # Everything as written, but for the trace context the outbox fills in.
    assert replace(EventEnvelope.from_json(body), trace_context={}) == event


def test_an_event_carries_the_trace_it_was_published_in(
    engine: Engine, channel: BlockingChannel, spans: InMemorySpanExporter
) -> None:
    queue = queue_bound_to(channel, "widget.traced.v1")

    with trace.get_tracer(__name__).start_as_current_span("request") as request:
        commit(engine, an_event("widget.traced.v1"))

    _, body = next_message(channel, queue)
    publish = the_one_span(spans, SpanKind.PRODUCER)
    assert publish.parent is not None
    assert publish.parent.span_id == request.get_span_context().span_id
    published_in = trace.format_trace_id(request.get_span_context().trace_id)
    assert published_in in EventEnvelope.from_json(body).trace_context["traceparent"]


def test_a_rolled_back_event_is_never_published(engine: Engine, channel: BlockingChannel) -> None:
    queue = queue_bound_to(channel, "widget.scrapped.v1")
    rolled_back, committed = an_event("widget.scrapped.v1"), an_event("widget.scrapped.v1")

    roll_back(engine, rolled_back)
    commit(engine, committed)

    # Events arrive in commit order, so had the rolled-back one been published, it'd be first.
    _, body = next_message(channel, queue)
    assert EventEnvelope.from_json(body).event_id == committed.event_id


def test_the_outbox_is_empty_after_a_commit(engine: Engine) -> None:
    commit(engine, an_event("widget.counted.v1"))

    with unit_of_work(engine, "throwaway") as session:
        assert session.scalar(text("SELECT count(*) FROM outbox")) == 0


def test_events_committed_while_debezium_is_down_arrive_once_it_is_back(
    engine: Engine, channel: BlockingChannel, debezium: DockerContainer
) -> None:
    queue = queue_bound_to(channel, "widget.shipped.v1")
    commit(engine, an_event("widget.shipped.v1"))
    next_message(channel, queue)  # Debezium is streaming
    event = an_event("widget.shipped.v1")

    debezium.get_wrapped_container().stop()
    commit(engine, event)
    debezium.get_wrapped_container().start()

    _, body = next_message(channel, queue)
    assert EventEnvelope.from_json(body).event_id == event.event_id
