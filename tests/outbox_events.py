"""The integration events a context's outbox publishes, read from the write-ahead log as
Debezium Server reads them, but through a replication slot of the test's own."""

import re
from contextlib import contextmanager
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Engine, create_engine, text

from kart.shared.kernel.event_envelope import EventEnvelope

if TYPE_CHECKING:
    from collections.abc import Generator

# Postgres's test_decoding plugin writes each insert as text, quoting a value in single quotes
# and doubling any inside it, as in `payload[jsonb]:'{"note": "it''s"}'`.
_PAYLOAD = re.compile(r"payload\[jsonb\]:'((?:[^']|'')*)'")


class OutboxEvents:
    def __init__(self, engine: Engine, slot: str, context: str) -> None:
        self._engine = engine
        self._slot = slot
        self._inserts = f"table {context}.outbox: INSERT:"

    def published(self) -> list[EventEnvelope]:
        """Every event the context's outbox has published since the watch began, in order."""
        with self._engine.connect() as connection:
            changes = connection.scalars(
                text("SELECT data FROM pg_logical_slot_peek_changes(:slot, NULL, NULL)"),
                {"slot": self._slot},
            )
            return [_envelope(change) for change in changes if change.startswith(self._inserts)]


@contextmanager
def watching_outbox(database_url: str, context: str) -> Generator[OutboxEvents]:
    """Watch `context`'s outbox from now on."""
    engine = create_engine(database_url, isolation_level="AUTOCOMMIT")
    slot = f"test_{uuid4().hex}"
    with engine.connect() as connection:
        connection.execute(
            text("SELECT pg_create_logical_replication_slot(:slot, 'test_decoding')"),
            {"slot": slot},
        )
    try:
        yield OutboxEvents(engine, slot, context)
    finally:
        with engine.connect() as connection:
            connection.execute(text("SELECT pg_drop_replication_slot(:slot)"), {"slot": slot})
        engine.dispose()


def _envelope(insert: str) -> EventEnvelope:
    payload = _PAYLOAD.search(insert)
    if payload is None:
        msg = f"an outbox insert without a payload: {insert}"
        raise AssertionError(msg)
    return EventEnvelope.from_json(payload[1].replace("''", "'"))
