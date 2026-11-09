"""The one database engine every context shares, and the unit of work they're handed.

Contexts never build engines: the app creates one and gives each context units of work
for its own schema.
"""

from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from collections.abc import Generator


def create_database_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


@contextmanager
def unit_of_work(engine: Engine, context: str) -> Generator[Session]:
    """One transaction for `context`, committed if the block succeeds, else rolled back.

    It runs as the context's role (ADR-0008), so Postgres refuses any
    statement that touches another context's schema, and unqualified names resolve to the
    context's own schema.
    """
    with Session(engine) as session, session.begin():
        enter_context(session.connection(), context)
        yield session


def enter_context(connection: Connection, context: str) -> None:
    """Run the rest of `connection`'s transaction as `context`'s role, in its schema."""
    identifier = connection.dialect.identifier_preparer.quote(context)
    connection.execute(text(f"SET LOCAL ROLE {identifier}"))
    connection.execute(text(f"SET LOCAL search_path TO {identifier}"))
