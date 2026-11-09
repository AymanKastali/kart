"""Consuming integration events: the worker hands each one to the subscribing context's handler
in a unit of work that also records it in the context's inbox."""

import io
import json
import logging
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING
from uuid import uuid4

import pika
import pytest
from opentelemetry import trace
from opentelemetry.trace import SpanKind
from sqlalchemy import Engine, text
from sqlalchemy.orm.exc import StaleDataError

from kart.app.database import unit_of_work
from kart.app.observability import JsonLogFormatter
from kart.app.rabbitmq_setup import EVENTS_EXCHANGE, set_up_rabbitmq
from kart.app.worker import ATTEMPTS, consume
from kart.shared.inbox import Subscription
from kart.shared.kernel.event_envelope import EventEnvelope
from kart.shared.outbox import write_to_outbox
from tests.conftest import the_one_span
from tests.shared.conftest import an_event, eventually, rabbitmq_url

if TYPE_CHECKING:
    from collections.abc import Generator

    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from pika.adapters.blocking_connection import BlockingChannel
    from sqlalchemy.orm import Session
    from testcontainers.community.rabbitmq import RabbitMqContainer

SUBSCRIBER = "subscriber"


def record(session: Session, event: EventEnvelope) -> None:
    """The subscriber's reaction to an event: a row in its `handled` table."""
    session.execute(text("INSERT INTO handled VALUES (:id)"), {"id": event.event_id})


class ScriptedHandler:
    """Records each event, after failing the first `failures` times with `error`."""

    def __init__(self, failures: int = 0, error: Exception | None = None) -> None:
        self.failures = failures
        self.error = error or RuntimeError("The handler failed")
        self.calls = 0

    def __call__(self, session: Session, event: EventEnvelope) -> None:
        self.calls += 1
        record(session, event)
        if self.calls <= self.failures:
            raise self.error


@contextmanager
def consuming(
    rabbitmq: RabbitMqContainer, engine: Engine, subscription: Subscription
) -> Generator[None]:
    """Run the worker for `subscription` in the background, then remove its queues."""
    url = rabbitmq_url(rabbitmq)
    set_up_rabbitmq(url, [subscription])
    stopped = threading.Event()
    worker = threading.Thread(target=consume, args=(url, engine, [subscription], stopped))
    worker.start()
    try:
        yield
    finally:
        stopped.set()
        worker.join()
        connection = pika.BlockingConnection(pika.URLParameters(url))
        connection.channel().queue_delete(subscription.queue)
        connection.channel().queue_delete(subscription.dead_letter_queue)
        connection.close()


def publish(channel: BlockingChannel, event: EventEnvelope) -> None:
    """Deliver `event` as Debezium would, without the outbox."""
    channel.basic_publish(EVENTS_EXCHANGE, event.type, event.to_json().encode())


def next_event(channel: BlockingChannel, queue: str) -> EventEnvelope:
    def get() -> EventEnvelope | None:
        method, _, body = channel.basic_get(queue, auto_ack=True)
        return EventEnvelope.from_json(body.decode()) if method and body else None

    return eventually(get, f"An event on {queue}")


def rows_for(engine: Engine, table: str, event: EventEnvelope) -> int:
    """How many rows of the subscriber's `table` name `event`."""
    with unit_of_work(engine, SUBSCRIBER) as session:
        return session.scalar(
            text(f"SELECT count(*) FROM {table} WHERE event_id = :id"),  # noqa: S608 a fixed name
            {"id": event.event_id},
        )


def times_handled(engine: Engine, event: EventEnvelope) -> int:
    return rows_for(engine, "handled", event)


def was_handled(engine: Engine, event: EventEnvelope) -> bool | None:
    """True once `event` has been handled, for `eventually`."""
    return True if times_handled(engine, event) else None


@pytest.mark.usefixtures("debezium")
def test_an_event_published_through_the_outbox_is_handled_once_even_if_delivered_twice(
    engine: Engine, rabbitmq: RabbitMqContainer, channel: BlockingChannel
) -> None:
    handler = ScriptedHandler()
    subscription = Subscription(SUBSCRIBER, {"widget.made.v1": handler})
    event, later = an_event("widget.made.v1"), an_event("widget.made.v1")

    with consuming(rabbitmq, engine, subscription):
        with unit_of_work(engine, "throwaway") as session:
            write_to_outbox(session, event, aggregate_type="widget", aggregate_id=uuid4())
        eventually(lambda: was_handled(engine, event), "Handling the event")
        publish(channel, event)  # redelivered
        publish(channel, later)
        # One queue, handled in order, so once `later` is handled the duplicate has been too.
        eventually(lambda: was_handled(engine, later), "Handling the later event")

    assert times_handled(engine, event) == 1
    assert handler.calls == 2


@pytest.mark.usefixtures("debezium")
def test_handling_an_event_continues_the_trace_that_published_it(
    engine: Engine, rabbitmq: RabbitMqContainer, spans: InMemorySpanExporter
) -> None:
    traces_handled_in: list[int] = []

    def handler(session: Session, event: EventEnvelope) -> None:
        traces_handled_in.append(trace.get_current_span().get_span_context().trace_id)
        record(session, event)

    subscription = Subscription(SUBSCRIBER, {"widget.traced.v1": handler})
    event = an_event("widget.traced.v1")

    with consuming(rabbitmq, engine, subscription):
        with (
            trace.get_tracer(__name__).start_as_current_span("request") as request,
            unit_of_work(engine, "throwaway") as session,
        ):
            write_to_outbox(session, event, aggregate_type="widget", aggregate_id=uuid4())
        eventually(lambda: was_handled(engine, event), "Handling the event")

    published_in = request.get_span_context().trace_id
    consumer = the_one_span(spans, SpanKind.CONSUMER)
    assert consumer.name == f"process {subscription.queue}"
    assert consumer.context.trace_id == published_in
    assert traces_handled_in == [published_in]


@pytest.mark.usefixtures("debezium", "spans")
def test_a_failed_handlers_log_line_carries_the_trace_that_published_the_event(
    engine: Engine, rabbitmq: RabbitMqContainer
) -> None:
    subscription = Subscription(SUBSCRIBER, {"widget.dropped.v1": ScriptedHandler(failures=1)})
    event = an_event("widget.dropped.v1")
    log = io.StringIO()
    handler = logging.StreamHandler(log)
    handler.setFormatter(JsonLogFormatter())
    logging.getLogger("kart.app.worker").addHandler(handler)

    try:
        with consuming(rabbitmq, engine, subscription):
            with (
                trace.get_tracer(__name__).start_as_current_span("request") as request,
                unit_of_work(engine, "throwaway") as session,
            ):
                write_to_outbox(session, event, aggregate_type="widget", aggregate_id=uuid4())
            eventually(lambda: was_handled(engine, event), "Handling the retried event")
    finally:
        logging.getLogger("kart.app.worker").removeHandler(handler)

    [failure] = [json.loads(line) for line in log.getvalue().splitlines()]
    assert failure["trace_id"] == trace.format_trace_id(request.get_span_context().trace_id)


def test_a_handler_that_always_fails_sends_the_event_to_the_dead_letter_queue(
    engine: Engine, rabbitmq: RabbitMqContainer, channel: BlockingChannel
) -> None:
    handler = ScriptedHandler(failures=1_000)
    subscription = Subscription(SUBSCRIBER, {"widget.scrapped.v1": handler})
    event = an_event("widget.scrapped.v1")

    with consuming(rabbitmq, engine, subscription):
        publish(channel, event)
        dead_letter = next_event(channel, subscription.dead_letter_queue)

    assert dead_letter == event
    assert handler.calls == ATTEMPTS
    assert times_handled(engine, event) == 0
    assert rows_for(engine, "inbox", event) == 0


def test_a_handler_that_loses_an_optimistic_concurrency_race_is_retried(
    engine: Engine, rabbitmq: RabbitMqContainer, channel: BlockingChannel
) -> None:
    handler = ScriptedHandler(failures=1, error=StaleDataError("The order changed underneath"))
    subscription = Subscription(SUBSCRIBER, {"widget.counted.v1": handler})
    event = an_event("widget.counted.v1")

    with consuming(rabbitmq, engine, subscription):
        publish(channel, event)
        eventually(lambda: was_handled(engine, event), "Handling the event")

    assert times_handled(engine, event) == 1
    assert handler.calls == 2
