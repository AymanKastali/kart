from typing import TYPE_CHECKING

from sqlalchemy import create_engine, text

from kart.app.migrate import migrate

if TYPE_CHECKING:
    from collections.abc import Sequence

CONTEXTS = [
    "catalog",
    "discovery",
    "fulfilment",
    "identity",
    "notification",
    "offer",
    "ordering",
    "payment",
    "seller_onboarding",
    "seller_settlement",
]


def _version_tables(database_url: str) -> dict[str, Sequence[str]]:
    """Each schema that has an Alembic version table, with the revisions it records."""
    engine = create_engine(database_url)
    with engine.connect() as connection:
        schemas = connection.scalars(
            text(
                "SELECT table_schema FROM information_schema.tables"
                " WHERE table_name = 'alembic_version' ORDER BY table_schema"
            )
        ).all()
        versions = {
            schema: connection.scalars(
                text(f'SELECT version_num FROM "{schema}".alembic_version')  # noqa: S608 a catalog name
            ).all()
            for schema in schemas
        }
    engine.dispose()
    return versions


def test_migrate_gives_every_context_its_own_schema_and_version_table(
    empty_database_url: str,
) -> None:
    migrate(empty_database_url)

    versions = _version_tables(empty_database_url)
    assert list(versions) == CONTEXTS
    assert all(revisions == ["0001"] for revisions in versions.values())


def test_migrating_again_changes_nothing(empty_database_url: str) -> None:
    migrate(empty_database_url)
    before = _version_tables(empty_database_url)

    migrate(empty_database_url)

    assert _version_tables(empty_database_url) == before
