"""Real infrastructure for the tests that need it, started once per test run and only if a test
asks for it."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, make_url, text
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.network import Network

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(scope="session")
def network() -> Iterator[Network]:
    """A Docker network, so containers such as Debezium can reach Postgres by name."""
    with Network() as network:
        yield network


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
