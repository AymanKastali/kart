"""Real infrastructure for the tests that need it, started once per test run and only if a test
asks for it."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import create_engine, make_url, text
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network
from testcontainers.core.wait_strategies import HttpWaitStrategy

from tests.mailpit import Mailpit

if TYPE_CHECKING:
    from collections.abc import Iterator

    from opentelemetry.sdk.trace import ReadableSpan
    from opentelemetry.trace import SpanKind


@pytest.fixture(scope="session")
def _span_exporter() -> InMemorySpanExporter:
    # The tracer provider can be set once per process, so every test shares this one.
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return exporter


@pytest.fixture
def spans(_span_exporter: InMemorySpanExporter) -> InMemorySpanExporter:
    """Every span the test finishes, recorded in memory."""
    _span_exporter.clear()
    return _span_exporter


def the_one_span(spans: InMemorySpanExporter, kind: SpanKind) -> ReadableSpan:
    """The one finished span of `kind`, failing if there are none or several."""
    [span] = [span for span in spans.get_finished_spans() if span.kind == kind]
    return span


@pytest.fixture(scope="session")
def network() -> Iterator[Network]:
    """A Docker network, so containers such as Debezium can reach Postgres by name."""
    with Network() as network:
        yield network


@pytest.fixture(scope="session")
def mailpit(network: Network) -> Iterator[Mailpit]:
    """A Mailpit, as in Compose, catching the email sent to its SMTP port at `mailpit:1025`."""
    container = (
        DockerContainer("axllent/mailpit:v1.33")
        .with_network(network)
        .with_network_aliases("mailpit")
        .with_exposed_ports(8025)
        .waiting_for(HttpWaitStrategy(8025, "/readyz"))
    )
    with container:
        yield Mailpit(
            f"http://{container.get_container_host_ip()}:{container.get_exposed_port(8025)}"
        )


@pytest.fixture(scope="session")
def postgres(network: Network) -> Iterator[PostgresContainer]:
    # Configured as in Compose for logical decoding. Every migrated database gets its own
    # replication slot, so there are plenty of them.
    container = (
        PostgresContainer("postgres:18", driver="psycopg")
        .with_command("postgres -c wal_level=logical -c max_replication_slots=100")
        .with_network(network)
        .with_network_aliases("postgres")
    )
    with container:
        yield container


def new_database(postgres: PostgresContainer) -> str:
    """The URL of a new, empty database."""
    server_url = postgres.get_connection_url()
    name = f"test_{uuid4().hex}"
    server = create_engine(server_url, isolation_level="AUTOCOMMIT")
    with server.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    server.dispose()
    return make_url(server_url).set(database=name).render_as_string(hide_password=False)


@pytest.fixture
def empty_database_url(postgres: PostgresContainer) -> str:
    """A new, empty database, so each test starts from nothing."""
    return new_database(postgres)
