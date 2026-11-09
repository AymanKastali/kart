from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from kart.shared.kernel.event_envelope import EventEnvelope


def an_envelope() -> EventEnvelope:
    return EventEnvelope(
        event_id=UUID("0190a6e2-7c3b-7d4e-9f00-1234567890ab"),
        type="order.confirmed.v1",
        occurred_at=datetime(2026, 11, 9, 6, 7, 44, 123456, tzinfo=UTC),
        trace_context={"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"},
        payload={
            "order_number": "KAE7F3K9Q2XM",
            "total_fils": 129900,
            "cash_on_delivery": True,
            "groups": [{"shipment_number": "KAE7F3K9Q2XM-1", "lines": [], "note": None}],
        },
    )


def test_an_envelope_survives_a_json_round_trip_unchanged() -> None:
    envelope = an_envelope()

    assert EventEnvelope.from_json(envelope.to_json()) == envelope


@pytest.mark.parametrize(
    "event_type",
    ["order.confirmed", "order.confirmed.V1", "Order.Confirmed.v1", "confirmed.v1", ""],
)
def test_a_type_without_a_context_name_and_version_is_refused(event_type: str) -> None:
    with pytest.raises(ValueError, match="type"):
        replace(an_envelope(), type=event_type)


def test_a_time_without_a_timezone_is_refused() -> None:
    with pytest.raises(ValueError, match="timezone"):
        replace(an_envelope(), occurred_at=datetime(2026, 11, 9, 6, 7, 44))  # noqa: DTZ001


def test_a_payload_that_is_not_valid_json_is_refused() -> None:
    envelope = replace(an_envelope(), payload={"total": float("nan")})

    with pytest.raises(ValueError, match="JSON"):
        envelope.to_json()
