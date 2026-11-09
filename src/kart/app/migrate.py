"""Migrates every context's schema to its latest revision: `python -m kart.app.migrate`.

Each context has its own Alembic history in its `migrations` package and its own version
table inside its own schema. They share one Alembic environment, `kart.app.migrations`.
Then it prepares change data capture, so Debezium can read every context's outbox. Running it
again is a no-op, so Compose runs it on every `up`.
"""

import pkgutil
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

import kart.contexts
from kart.app.database import create_database_engine
from kart.app.settings import Settings

_ENVIRONMENT = Path(__file__).with_name("migrations")
_CONTEXTS = Path(kart.contexts.__file__).parent
# Debezium Server reads the outboxes through these (deploy/debezium/application.properties).
# A publication belongs to its database, but slot names are shared by the whole server, so
# the slot is named after the database.
_PUBLICATION = "outbox"
_SLOT_TEMPLATE = "{database}_outbox"


def contexts(directory: Path = _CONTEXTS) -> list[str]:
    """Every bounded context, named as its package and its schema are."""
    return sorted(module.name for module in pkgutil.iter_modules([str(directory)]) if module.ispkg)


def migrate(database_url: str, directory: Path = _CONTEXTS) -> None:
    """Migrate each context package in `directory`: Kart's own, unless a test brings its own."""
    for context in contexts(directory):
        config = Config()
        config.set_main_option("script_location", str(_ENVIRONMENT))
        config.set_main_option("path_separator", "os")
        config.set_main_option("version_locations", str(directory / context / "migrations"))
        # Passed as attributes, not options: options interpolate `%`, which escaped URLs use.
        config.attributes["database_url"] = database_url
        config.attributes["context"] = context
        command.upgrade(config, "head")
    _prepare_change_data_capture(database_url, contexts(directory))


def _prepare_change_data_capture(database_url: str, schemas: list[str]) -> None:
    """Make sure the publication covers every context's outbox, and the slot exists.

    The slot exists from the first migration on, so Postgres keeps every event committed
    before Debezium first connects, or while it is down. A table must be in the publication
    before events are written to it, which is why this runs before the app starts.
    """
    engine = create_database_engine(database_url)
    with engine.begin() as connection:
        if not connection.scalar(
            text("SELECT EXISTS (SELECT FROM pg_publication WHERE pubname = :name)"),
            {"name": _PUBLICATION},
        ):
            connection.execute(text(f"CREATE PUBLICATION {_PUBLICATION}"))
        unpublished = connection.scalars(
            text(
                "SELECT format('%I.%I', table_schema, table_name)"
                " FROM information_schema.tables"
                " WHERE table_name = 'outbox' AND table_schema = ANY(:schemas)"
                " AND (table_schema, table_name) NOT IN"
                " (SELECT schemaname, tablename FROM pg_publication_tables WHERE pubname = :name)"
            ),
            {"schemas": schemas, "name": _PUBLICATION},
        ).all()
        for table in unpublished:
            connection.execute(text(f"ALTER PUBLICATION {_PUBLICATION} ADD TABLE {table}"))
    # Its own transaction: Postgres refuses to create a slot in one that has written.
    with engine.begin() as connection:
        slot = _SLOT_TEMPLATE.format(database=connection.scalar(text("SELECT current_database()")))
        if not connection.scalar(
            text("SELECT EXISTS (SELECT FROM pg_replication_slots WHERE slot_name = :name)"),
            {"name": slot},
        ):
            connection.execute(
                text("SELECT pg_create_logical_replication_slot(:name, 'pgoutput')"),
                {"name": slot},
            )
    engine.dispose()


if __name__ == "__main__":
    migrate(Settings().database_url)
