"""The inbox a context consumes integration events through (ADR-0004).

A context subscribes with a handler per event type. The worker runs each handler in a unit of
work that also inserts the event's id into the context's `inbox` table, so a redelivered event
finds its id already there and isn't handled again. A handler that fails rolls the inbox row
back with everything else, so the event is retried. The handler is handed the context's
repository bound to that transaction, never the session itself (ADR-0012).
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from alembic import op
from sqlalchemy import Column, MetaData, Table, Uuid
from sqlalchemy.dialects.postgresql import insert

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from uuid import UUID

    from sqlalchemy.orm import Session

    from kart.shared.kernel.event_envelope import EventEnvelope

type Handler[R] = Callable[[R, EventEnvelope], None]

_inbox = Table("inbox", MetaData(), Column("event_id", Uuid, primary_key=True))


@dataclass(frozen=True, slots=True)
class Subscription[R]:
    """The events `context` reacts to, each with the handler that reacts to it, and the
    `repository` each handler is handed, bound to the transaction it runs in."""

    context: str
    repository: Callable[[Session], R]
    handlers: Mapping[str, Handler[R]]

    @property
    def queue(self) -> str:
        return f"{self.context}.q"

    @property
    def dead_letter_queue(self) -> str:
        return f"{self.context}.dlq"


def create_inbox_table() -> None:
    """Create the inbox in the context's schema. Call it from one of the context's revisions."""
    _inbox.create(op.get_bind())


def drop_inbox_table() -> None:
    """Drop the inbox from the context's schema, in the revision's downgrade."""
    _inbox.drop(op.get_bind())


def record_in_inbox(session: Session, event_id: UUID) -> bool:
    """Record `event_id` as handled in `session`'s transaction. False if it already was, so
    the event mustn't be handled again."""
    inserted = session.scalar(
        insert(_inbox)
        .values(event_id=event_id)
        .on_conflict_do_nothing()
        .returning(_inbox.c.event_id)
    )
    return inserted is not None
