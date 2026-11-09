"""A real Postgres for the database tests, started once per test run."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, make_url, text
from testcontainers.community.postgres import PostgresContainer

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(scope="session")
def postgres() -> Iterator[PostgresContainer]:
    with PostgresContainer("postgres:18", driver="psycopg") as container:
        yield container


@pytest.fixture
def empty_database_url(postgres: PostgresContainer) -> str:
    """The URL of a new, empty database, so each test starts from nothing."""
    server_url = postgres.get_connection_url()
    name = f"test_{uuid4().hex}"
    server = create_engine(server_url, isolation_level="AUTOCOMMIT")
    with server.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    server.dispose()
    return make_url(server_url).set(database=name).render_as_string(hide_password=False)
