"""The outbox end to end: a context commits an event, Debezium Server captures it from the
write-ahead log, and RabbitMQ delivers it."""

import contextlib
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text

from kart.app.database import unit_of_work
from kart.app.topology import EVENTS_EXCHANGE
from kart.building_blocks.outbox import write_to_outbox
from kart.shared_kernel.event_envelope import EventEnvelope
from tests.building_blocks.conftest import eventually

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pika.adapters.blocking_connection import BlockingChannel
    from testcontainers.core.container import DockerContainer

# Events flow only while Debezium runs.
pytestmark = pytest.mark.usefixtures("debezium")


def an_event(event_type: str) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid4(),
        type=event_type,
        occurred_at=datetime.now(UTC),
        trace_context={"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"},
        payload={"widget_id": "W-1", "quantity": 3, "gift": True, "note": None},
    )


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
    assert EventEnvelope.from_json(body) == event


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
