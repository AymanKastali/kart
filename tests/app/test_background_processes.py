import json
import os
import signal
import subprocess
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest

from tests.app.environment import ENVIRONMENT

if TYPE_CHECKING:
    from collections.abc import Generator

BACKGROUND_PROCESSES = ["worker", "scheduler"]


@contextmanager
def started(process: str) -> Generator[subprocess.Popen[str]]:
    """The process running as `python -m kart.app.<process>`, killed on exit if still running."""
    running = subprocess.Popen(  # noqa: S603 the command is fixed
        [sys.executable, "-m", f"kart.app.{process}"],
        stdout=subprocess.PIPE,
        env={**os.environ, **ENVIRONMENT},
        text=True,
    )
    try:
        yield running
    finally:
        running.kill()


def first_log_line(running: subprocess.Popen[str]) -> dict[str, str]:
    assert running.stdout is not None
    return json.loads(running.stdout.readline())


@pytest.mark.parametrize("process", BACKGROUND_PROCESSES)
def test_a_background_process_announces_itself_in_json(process: str) -> None:
    # No OTLP endpoint or Sentry DSN is set, so it runs without exporting anything.
    with started(process) as running:
        line = first_log_line(running)

    assert line["message"] == f"{process} started"


@pytest.mark.parametrize("process", BACKGROUND_PROCESSES)
def test_a_background_process_stops_cleanly_on_sigterm(process: str) -> None:
    with started(process) as running:
        first_log_line(running)  # it has started

        running.send_signal(signal.SIGTERM)

        assert running.wait(timeout=5) == 0
