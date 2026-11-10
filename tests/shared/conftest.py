"""Messaging infrastructure, started once per test module: a database migrated with the
throwaway contexts in `contexts/`, RabbitMQ with Kart's exchange, and Debezium Server with the
configuration Compose mounts."""

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pika
import pytest
from sqlalchemy import Engine, make_url
from testcontainers.community.rabbitmq import RabbitMqContainer
from testcontainers.core.container import DockerContainer

from kart.app.database import create_database_engine, transaction
from kart.app.migrate import migrate
from kart.app.rabbitmq_setup import set_up_rabbitmq
from kart.shared.kernel.event_envelope import EventEnvelope
from kart.shared.outbox import write_to_outbox
from tests.conftest import new_database

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

    from pika.adapters.blocking_connection import BlockingChannel
    from testcontainers.community.postgres import PostgresContainer
    from testcontainers.core.network import Network

# tests/shared/<this file> -> the repository root.
REPO_ROOT = Path(__file__).resolve().parents[2]
THROWAWAY_CONTEXTS = Path(__file__).with_name("contexts")
# The throwaway context that publishes events in these tests.
THROWAWAY = "throwaway"
RABBITMQ_USER = "kart"
RABBITMQ_PASSWORD = "kart"  # noqa: S105 a throwaway broker
# Long enough for Debezium to start, connect and catch up.
TIMEOUT_SECONDS = 60


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
        set_up_rabbitmq(rabbitmq_url(container), [])
        yield container


def rabbitmq_url(rabbitmq: RabbitMqContainer) -> str:
    params = rabbitmq.get_connection_params()
    return f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{params.host}:{params.port}/"


@pytest.fixture(scope="module")
def debezium(
    network: Network, database_url: str, rabbitmq: RabbitMqContainer
) -> Iterator[DockerContainer]:
    url = make_url(database_url)
    container = (
        DockerContainer("quay.io/debezium/server:3.7.1.Final")
        .with_volume_mapping(
            REPO_ROOT / "debezium/application.properties", "/debezium/config/application.properties"
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
        payload={"widget_id": "W-1", "quantity": 3, "gift": True, "note": None},
    )


def publish_through_outbox(engine: Engine, event: EventEnvelope) -> None:
    """Commit `event` to the throwaway context's outbox, as a context's use case would."""
    with transaction(engine, THROWAWAY) as session:
        write_to_outbox(session, event, aggregate_type="widget", aggregate_id=uuid4())


def next_message(channel: BlockingChannel, queue: str) -> tuple[Mapping[str | bytes, object], str]:
    """The headers and body of the next message on `queue`, waiting for it to arrive."""

    def get() -> tuple[Mapping[str | bytes, object], str] | None:
        method, properties, body = channel.basic_get(queue, auto_ack=True)
        if method is None or properties is None or body is None:
            return None
        return properties.headers or {}, body.decode()

    return eventually(get, f"A message on {queue}")


def wait_until(condition: Callable[[], bool], what: str) -> None:
    """Wait for `condition` to hold, trying until the timeout."""
    eventually(lambda: True if condition() else None, what)


def eventually[T](check: Callable[[], T | None], what: str) -> T:
    """The first result of `check` that isn't None, trying until the timeout."""
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if (result := check()) is not None:
            return result
        time.sleep(0.2)
    pytest.fail(f"{what} didn't happen within {TIMEOUT_SECONDS}s")
