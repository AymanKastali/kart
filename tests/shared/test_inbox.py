"""Consuming integration events: the worker hands each one to the subscribing context's handler
in a unit of work that also records it in the context's inbox."""

import io
import json
import logging
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING

import pika
import pytest
from opentelemetry import trace
from opentelemetry.trace import SpanKind
from sqlalchemy import Engine, text
from sqlalchemy.orm.exc import StaleDataError

from kart.app.database import transaction
from kart.app.observability import JsonLogFormatter
from kart.app.rabbitmq_setup import EVENTS_EXCHANGE, set_up_rabbitmq
from kart.app.worker import ATTEMPTS, consume
from kart.shared.inbox import Subscription
from kart.shared.kernel.event_envelope import EventEnvelope
from tests.conftest import the_one_span
from tests.shared.conftest import (
    an_event,
    next_message,
    publish_through_outbox,
    rabbitmq_url,
    wait_until,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from pika.adapters.blocking_connection import BlockingChannel
    from sqlalchemy.orm import Session
    from testcontainers.community.rabbitmq import RabbitMqContainer

SUBSCRIBER = "subscriber"


class Handled:
    """The subscriber's repository: its reaction to an event is a row in its `handled` table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, event: EventEnvelope) -> None:
        self._session.execute(text("INSERT INTO handled VALUES (:id)"), {"id": event.event_id})


class ScriptedHandler:
    """Records each event, after failing the first `failures` times with `error`."""

    def __init__(self, failures: int = 0, error: Exception | None = None) -> None:
        self.failures = failures
        self.error = error or RuntimeError("The handler failed")
        self.calls = 0

    def __call__(self, handled: Handled, event: EventEnvelope) -> None:
        self.calls += 1
        handled.record(event)
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
    worker = threading.Thread(
        target=consume, args=(url, engine, [subscription]), kwargs={"stopped": stopped}
    )
    worker.start()
    try:
        yield
    finally:
        stopped.set()
        worker.join()
        delete_queues(url, subscription)


def delete_queues(rabbitmq_url: str, subscription: Subscription) -> None:
    connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
    connection.channel().queue_delete(subscription.queue)
    connection.channel().queue_delete(subscription.dead_letter_queue)
    connection.close()


def publish(channel: BlockingChannel, event: EventEnvelope) -> None:
    """Deliver `event` as Debezium would, without the outbox."""
    channel.basic_publish(EVENTS_EXCHANGE, event.type, event.to_json().encode())


def next_event(channel: BlockingChannel, queue: str) -> EventEnvelope:
    _, body = next_message(channel, queue)
    return EventEnvelope.from_json(body)


def rows_for(engine: Engine, table: str, event: EventEnvelope) -> int:
    """How many rows of the subscriber's `table` name `event`."""
    with transaction(engine, SUBSCRIBER) as session:
        return session.scalar(
            text(f"SELECT count(*) FROM {table} WHERE event_id = :id"),  # noqa: S608 a fixed name
            {"id": event.event_id},
        )


def times_handled(engine: Engine, event: EventEnvelope) -> int:
    return rows_for(engine, "handled", event)


def was_handled(engine: Engine, event: EventEnvelope) -> bool:
    return times_handled(engine, event) > 0


@pytest.mark.usefixtures("debezium")
def test_an_event_published_through_the_outbox_is_handled_once_even_if_delivered_twice(
    engine: Engine, rabbitmq: RabbitMqContainer, channel: BlockingChannel
) -> None:
    handler = ScriptedHandler()
    subscription = Subscription(SUBSCRIBER, Handled, {"widget.made.v1": handler})
    event, later = an_event("widget.made.v1"), an_event("widget.made.v1")

    with consuming(rabbitmq, engine, subscription):
        publish_through_outbox(engine, event)
        wait_until(lambda: was_handled(engine, event), "Handling the event")
        publish(channel, event)  # redelivered
        publish(channel, later)
        # One queue, handled in order, so once `later` is handled the duplicate has been too.
        wait_until(lambda: was_handled(engine, later), "Handling the later event")

    assert times_handled(engine, event) == 1


@pytest.mark.usefixtures("debezium")
def test_handling_an_event_continues_the_trace_that_published_it(
    engine: Engine, rabbitmq: RabbitMqContainer, spans: InMemorySpanExporter
) -> None:
    traces_handled_in: list[int] = []

    def handler(handled: Handled, event: EventEnvelope) -> None:
        traces_handled_in.append(trace.get_current_span().get_span_context().trace_id)
        handled.record(event)

    subscription = Subscription(SUBSCRIBER, Handled, {"widget.traced.v1": handler})
    event = an_event("widget.traced.v1")

    with consuming(rabbitmq, engine, subscription):
        with trace.get_tracer(__name__).start_as_current_span("request") as request:
            publish_through_outbox(engine, event)
        wait_until(lambda: was_handled(engine, event), "Handling the event")

    published_in = request.get_span_context().trace_id
    consumer = the_one_span(spans, SpanKind.CONSUMER)
    assert consumer.name == f"process {subscription.queue}"
    assert consumer.context.trace_id == published_in
    assert traces_handled_in == [published_in]


@contextmanager
def json_log_lines(logger_name: str) -> Generator[list[dict]]:
    """Every line the logger writes while inside, read back from JSON once it exits."""
    log = io.StringIO()
    handler = logging.StreamHandler(log)
    handler.setFormatter(JsonLogFormatter())
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    lines: list[dict] = []
    try:
        yield lines
    finally:
        logger.removeHandler(handler)
        lines.extend(json.loads(line) for line in log.getvalue().splitlines())


@pytest.mark.usefixtures("debezium", "spans")
def test_a_failed_handlers_log_line_carries_the_trace_that_published_the_event(
    engine: Engine, rabbitmq: RabbitMqContainer
) -> None:
    subscription = Subscription(
        SUBSCRIBER, Handled, {"widget.dropped.v1": ScriptedHandler(failures=1)}
    )
    event = an_event("widget.dropped.v1")

    with json_log_lines("kart.app.worker") as logged, consuming(rabbitmq, engine, subscription):
        with trace.get_tracer(__name__).start_as_current_span("request") as request:
            publish_through_outbox(engine, event)
        wait_until(lambda: was_handled(engine, event), "Handling the retried event")

    [failure] = logged
    assert failure["trace_id"] == trace.format_trace_id(request.get_span_context().trace_id)


def test_a_handler_that_always_fails_sends_the_event_to_the_dead_letter_queue(
    engine: Engine, rabbitmq: RabbitMqContainer, channel: BlockingChannel
) -> None:
    handler = ScriptedHandler(failures=ATTEMPTS)
    subscription = Subscription(SUBSCRIBER, Handled, {"widget.scrapped.v1": handler})
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
    subscription = Subscription(SUBSCRIBER, Handled, {"widget.counted.v1": handler})
    event = an_event("widget.counted.v1")

    with consuming(rabbitmq, engine, subscription):
        publish(channel, event)
        wait_until(lambda: was_handled(engine, event), "Handling the event")

    assert times_handled(engine, event) == 1
    assert handler.calls == 2
