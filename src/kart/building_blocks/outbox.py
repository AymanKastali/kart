"""The transactional outbox a context publishes integration events through (ADR-0004).

Each context has its own `outbox` table, in Debezium's outbox layout. Writing an event
inserts a row and deletes it again in the caller's transaction, so the table stays empty: the
row exists only in the write-ahead log. Once the transaction commits, Debezium Server reads
it from there and publishes it to RabbitMQ. A rolled-back transaction leaves nothing to read.

The message body is the whole envelope as JSON, trace context included. The other columns
copy what Debezium needs to route the event and set its `id` header.
"""

from typing import TYPE_CHECKING

from alembic import op
from sqlalchemy import Column, MetaData, String, Table, Uuid, cast, delete, insert, literal
from sqlalchemy.dialects.postgresql import JSONB

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

    from kart.shared_kernel.event_envelope import EventEnvelope

_outbox = Table(
    "outbox",
    MetaData(),
    Column("id", Uuid, primary_key=True),
    Column("aggregatetype", String(255), nullable=False),
    Column("aggregateid", String(255), nullable=False),
    Column("type", String(255), nullable=False),
    Column("payload", JSONB, nullable=False),
)


def create_outbox_table() -> None:
    """Create the outbox in the context's schema. Call it from one of the context's revisions."""
    _outbox.create(op.get_bind())


def write_to_outbox(
    session: Session, envelope: EventEnvelope, *, aggregate_type: str, aggregate_id: UUID
) -> None:
    """Publish `envelope` once `session`'s transaction commits, and never if it rolls back."""
    session.execute(
        insert(_outbox).values(
            id=envelope.event_id,
            aggregatetype=aggregate_type,
            aggregateid=str(aggregate_id),
            type=envelope.type,
            payload=cast(literal(envelope.to_json(), String), JSONB),
        )
    )
    session.execute(delete(_outbox).where(_outbox.c.id == envelope.event_id))
