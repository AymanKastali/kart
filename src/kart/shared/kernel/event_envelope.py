import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

# For example order.confirmed.v1 or shipment.out_for_delivery.v2.
EVENT_TYPE_PATTERN = re.compile(r"[a-z][a-z_]*(\.[a-z][a-z_]*)+\.v[1-9][0-9]*")

type JsonValue = str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """What every integration event travels in, whichever context publishes it."""

    event_id: UUID
    type: str
    occurred_at: datetime
    payload: dict[str, JsonValue]
    # The W3C trace context (`traceparent`, `tracestate`) of the transaction that published it.
    # The outbox fills it in, so the consumer continues the publisher's trace.
    trace_context: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not EVENT_TYPE_PATTERN.fullmatch(self.type):
            msg = f"An event type is a dotted name ending in its version, not {self.type!r}"
            raise ValueError(msg)
        if self.occurred_at.utcoffset() is None:
            msg = f"The time an event happened needs a timezone: {self.occurred_at}"
            raise ValueError(msg)

    def to_json(self) -> str:
        return json.dumps(
            {
                "event_id": str(self.event_id),
                "type": self.type,
                "occurred_at": self.occurred_at.isoformat(),
                "trace_context": self.trace_context,
                "payload": self.payload,
            },
            allow_nan=False,
        )

    @classmethod
    def from_json(cls, text: str) -> EventEnvelope:
        data: dict[str, Any] = json.loads(text)
        return cls(
            event_id=UUID(data["event_id"]),
            type=data["type"],
            occurred_at=datetime.fromisoformat(data["occurred_at"]),
            trace_context=data["trace_context"],
            payload=data["payload"],
        )
