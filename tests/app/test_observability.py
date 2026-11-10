import json
import logging

import pytest
from opentelemetry import trace

from kart.app.observability import JsonLogFormatter

_tracer = trace.get_tracer(__name__)


def a_log_line(message: str, *, error: BaseException | None = None) -> dict[str, object]:
    """The line `message` is logged as, read back as JSON."""
    record = logging.getLogger("kart.test").makeRecord(
        "kart.test",
        logging.WARNING,
        __file__,
        1,
        message,
        (),
        (type(error), error, error.__traceback__) if error else None,
    )
    return json.loads(JsonLogFormatter().format(record))


def test_a_line_carries_its_message_level_and_logger() -> None:
    line = a_log_line("Order placed")

    assert line["message"] == "Order placed"
    assert line["level"] == "WARNING"
    assert line["logger"] == "kart.test"


@pytest.mark.usefixtures("spans")
def test_a_line_logged_inside_a_span_carries_its_trace_and_span_ids() -> None:
    with _tracer.start_as_current_span("request") as span:
        line = a_log_line("Order placed")

    assert line["trace_id"] == f"{span.get_span_context().trace_id:032x}"
    assert line["span_id"] == f"{span.get_span_context().span_id:016x}"


def test_a_line_logged_outside_any_span_has_no_trace_id() -> None:
    line = a_log_line("worker started")

    assert "trace_id" not in line
    assert "span_id" not in line


def test_a_logged_exception_is_part_of_the_line() -> None:
    message = "The handler failed"
    try:
        raise RuntimeError(message)  # noqa: TRY301 an exception with a traceback
    except RuntimeError as error:
        line = a_log_line("Handling failed", error=error)

    assert "RuntimeError: The handler failed" in str(line["exception"])
