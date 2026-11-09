"""The outbox end to end: a context commits an event, Debezium Server relays it from the
write-ahead log, and RabbitMQ delivers it.

Debezium runs with the configuration Compose mounts and RabbitMQ with Kart's topology, against
a database migrated with a throwaway context that has an outbox.
"""

import contextlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pika
import pytest
from sqlalchemy import Engine, make_url, text
from testcontainers.community.rabbitmq import RabbitMqContainer
from testcontainers.core.container import DockerContainer

from kart.app.database import create_database_engine, unit_of_work
from kart.app.migrate import migrate
from kart.app.topology import EVENTS_EXCHANGE, declare_topology
from kart.building_blocks.outbox import write_to_outbox
from kart.shared_kernel.event_envelope import EventEnvelope
from tests.conftest import new_database

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from pika.adapters.blocking_connection import BlockingChannel
    from testcontainers.community.postgres import PostgresContainer
    from testcontainers.core.network import Network

# tests/building_blocks/<this file> -> the repository root.
REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY = REPO_ROOT / "deploy"
THROWAWAY_CONTEXTS = Path(__file__).with_name("contexts")
RABBITMQ_USER = "kart"
RABBITMQ_PASSWORD = "kart"  # noqa: S105 a throwaway broker
# Long enough for Debezium to start, connect and catch up.
DELIVERY_TIMEOUT_SECONDS = 60

# Events flow only while Debezium runs.
pytestmark = pytest.mark.usefixtures("debezium")


@pytest.fixture(scope="module")
def database_url(postgres: PostgresContainer) -> str:
    url = new_database(postgres)
    migrate(url, THROWAWAY_CONTEXTS)
    return url


@pytest.fixture(scope="module")
def engine(database_url: str) -> Iterator[Engine]:
    engine = create_database_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def rabbitmq(network: Network) -> Iterator[RabbitMqContainer]:
    container = (
        RabbitMqContainer(
            "rabbitmq:4-management", username=RABBITMQ_USER, password=RABBITMQ_PASSWORD
        )
        .with_network(network)
        .with_network_aliases("rabbitmq")
    )
    with container:
        params = container.get_connection_params()
        declare_topology(f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{params.host}:{params.port}/")
        yield container


@pytest.fixture(scope="module")
def debezium(
    network: Network, database_url: str, rabbitmq: RabbitMqContainer
) -> Iterator[DockerContainer]:
    url = make_url(database_url)
    container = (
        DockerContainer("quay.io/debezium/server:3.7.1.Final")
        .with_volume_mapping(
            DEPLOY / "debezium/application.properties", "/debezium/config/application.properties"
        )
        .with_envs(
            POSTGRES_HOST="postgres",
            POSTGRES_USER=str(url.username),
            POSTGRES_PASSWORD=str(url.password),
            POSTGRES_DB=str(url.database),
            RABBITMQ_HOST="rabbitmq",
            RABBITMQ_DEFAULT_USER=rabbitmq.username,
            RABBITMQ_DEFAULT_PASS=rabbitmq.password,
        )
        .with_network(network)
    )
    with container:
        yield container


@pytest.fixture
def channel(rabbitmq: RabbitMqContainer) -> Iterator[BlockingChannel]:
    connection = pika.BlockingConnection(rabbitmq.get_connection_params())
    yield connection.channel()
    connection.close()


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
    deadline = time.monotonic() + DELIVERY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        method, properties, body = channel.basic_get(queue, auto_ack=True)
        if method is not None and properties is not None and body is not None:
            return properties.headers or {}, body.decode()
        time.sleep(0.2)
    pytest.fail(f"Nothing arrived on {queue} within {DELIVERY_TIMEOUT_SECONDS}s")


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
