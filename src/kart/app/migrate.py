"""Migrates every context's schema to its latest revision: `python -m kart.app.migrate`.

Each context has its own Alembic history in its `migrations` package and its own version
table inside its own schema. They share one Alembic environment, `kart.app.migrations`.
Running it again is a no-op, so Compose runs it on every `up`.
"""

import pkgutil
from pathlib import Path

from alembic import command
from alembic.config import Config

import kart.contexts
from kart.app.settings import Settings

_ENVIRONMENT = Path(__file__).with_name("migrations")
_CONTEXTS = Path(kart.contexts.__file__).parent


def contexts() -> list[str]:
    """Every bounded context, named as its package and its schema are."""
    return sorted(module.name for module in pkgutil.iter_modules([str(_CONTEXTS)]) if module.ispkg)


def migrate(database_url: str) -> None:
    for context in contexts():
        config = Config()
        config.set_main_option("script_location", str(_ENVIRONMENT))
        config.set_main_option("path_separator", "os")
        config.set_main_option("version_locations", str(_CONTEXTS / context / "migrations"))
        # Passed as attributes, not options: options interpolate `%`, which escaped URLs use.
        config.attributes["database_url"] = database_url
        config.attributes["context"] = context
        command.upgrade(config, "head")


if __name__ == "__main__":
    migrate(Settings().database_url)
