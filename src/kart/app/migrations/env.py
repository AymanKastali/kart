"""The Alembic environment every context's history runs in, one context at a time.

Before any revision runs, it makes sure the context has a role and a schema that role owns,
because Alembic creates the version table inside the schema first. Revisions then run as
that role, so everything they create belongs to the context.
"""

from alembic import context
from sqlalchemy import create_engine, text

name = context.config.attributes["context"]
engine = create_engine(context.config.attributes["database_url"])

with engine.begin() as connection:
    identifier = connection.dialect.identifier_preparer.quote(name)
    connection.execute(
        text(
            "DO $$ BEGIN"
            f" IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{name}')"
            f" THEN CREATE ROLE {identifier} NOLOGIN; END IF;"
            " END $$"
        )
    )
    connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {identifier} AUTHORIZATION {identifier}"))
    connection.execute(text(f"SET LOCAL ROLE {identifier}"))
    connection.execute(text(f"SET LOCAL search_path TO {identifier}"))
    context.configure(connection=connection, version_table_schema=name)
    with context.begin_transaction():
        context.run_migrations()

engine.dispose()
