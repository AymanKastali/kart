"""The Alembic environment every context's history runs in, one context at a time.

Before any revision runs, it makes sure the context has a role and a schema that role owns,
because Alembic creates the version table inside the schema first. So a context's first
revision has nothing left to create. Revisions then run as that role, so everything they
create belongs to the context.
"""

from alembic import context as alembic
from sqlalchemy import text

from kart.app.database import create_database_engine, enter_context

bounded_context = alembic.config.attributes["context"]
engine = create_database_engine(alembic.config.attributes["database_url"])

with engine.begin() as connection:
    identifier = connection.dialect.identifier_preparer.quote(bounded_context)
    role_exists = connection.scalar(
        text("SELECT EXISTS (SELECT FROM pg_roles WHERE rolname = :name)"),
        {"name": bounded_context},
    )
    if not role_exists:
        connection.execute(text(f"CREATE ROLE {identifier} NOLOGIN"))
    connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {identifier} AUTHORIZATION {identifier}"))
    enter_context(connection, bounded_context)
    alembic.configure(connection=connection, version_table_schema=bounded_context)
    with alembic.begin_transaction():
        alembic.run_migrations()

engine.dispose()
