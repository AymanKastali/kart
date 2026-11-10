"""The transactional outbox a context publishes integration events through (ADR-0004).

Each context has its own `outbox` table, in Debezium's outbox layout. Writing an event
inserts a row and deletes it again in the caller's transaction, so the table stays empty: the
row exists only in the write-ahead log. Once the transaction commits, Debezium Server reads
it from there and publishes it to RabbitMQ. A rolled-back transaction leaves nothing to read.

The message body is the whole envelope as JSON, trace context included. The other columns
copy what Debezium needs to route the event and set its `id` header. The trace context travels
in the body, not the `traceparent` header, because Debezium overwrites that header (ADR-0011).
"""

from dataclasses import replace
from typing import TYPE_CHECKING

from alembic import op
from opentelemetry import propagate, trace
from opentelemetry.trace import SpanKind
from sqlalchemy import Column, MetaData, String, Table, Uuid, cast, delete, insert, literal
from sqlalchemy.dialects.postgresql import JSONB

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

    from kart.shared.kernel.event_envelope import EventEnvelope

_tracer = trace.get_tracer(__name__)

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


def drop_outbox_table() -> None:
    """Drop the outbox from the context's schema, in the revision's downgrade."""
    _outbox.drop(op.get_bind())


def write_to_outbox(
    session: Session, envelope: EventEnvelope, *, aggregate_type: str, aggregate_id: UUID
) -> None:
    """Publish `envelope` once `session`'s transaction commits, and never if it rolls back.

    It goes out with the current trace context, so its consumers join the publisher's trace.
    """
    with _tracer.start_as_current_span(f"publish {envelope.type}", kind=SpanKind.PRODUCER):
        session.execute(
            insert(_outbox).values(
                id=envelope.event_id,
                aggregatetype=aggregate_type,
                aggregateid=str(aggregate_id),
                type=envelope.type,
                payload=cast(literal(_in_current_trace(envelope).to_json(), String), JSONB),
            )
        )
        session.execute(delete(_outbox).where(_outbox.c.id == envelope.event_id))


def _in_current_trace(envelope: EventEnvelope) -> EventEnvelope:
    trace_context: dict[str, str] = {}
    propagate.inject(trace_context)
    return replace(envelope, trace_context=trace_context)
