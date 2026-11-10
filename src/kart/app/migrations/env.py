"""The Alembic environment every context's history runs in, one context at a time.

Before any revision runs, it makes sure the context has a role and a schema that role owns,
because Alembic creates the version table inside the schema first. So a context's first
revision has nothing left to create. Revisions then run as that role, so everything they
create belongs to the context.
"""

from alembic import context as migration_context
from sqlalchemy import Connection, text

from kart.app.database import create_database_engine, enter_context


def _ensure_role_and_schema(connection: Connection, bounded_context: str) -> None:
    identifier = connection.dialect.identifier_preparer.quote(bounded_context)
    role_exists = connection.scalar(
        text("SELECT EXISTS (SELECT FROM pg_roles WHERE rolname = :name)"),
        {"name": bounded_context},
    )
    if not role_exists:
        connection.execute(text(f"CREATE ROLE {identifier} NOLOGIN"))
    connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {identifier} AUTHORIZATION {identifier}"))


bounded_context = migration_context.config.attributes["context"]
engine = create_database_engine(migration_context.config.attributes["database_url"])

with engine.begin() as connection:
    _ensure_role_and_schema(connection, bounded_context)
    enter_context(connection, bounded_context)
    migration_context.configure(connection=connection, version_table_schema=bounded_context)
    with migration_context.begin_transaction():
        migration_context.run_migrations()

engine.dispose()
