import json
import os
import signal
import subprocess
import sys

import pytest

from tests.app.test_settings import ENVIRONMENT


@pytest.mark.parametrize("process", ["worker", "scheduler"])
def test_a_background_process_logs_json_and_stops_cleanly_on_sigterm(process: str) -> None:
    running = subprocess.Popen(  # noqa: S603 the command is fixed
        [sys.executable, "-m", f"kart.app.{process}"],
        stdout=subprocess.PIPE,
        env={**os.environ, **ENVIRONMENT},
        text=True,
    )
    try:
        assert running.stdout is not None
        # No OTLP endpoint or Sentry DSN is set, so it runs without exporting anything.
        first_line = json.loads(running.stdout.readline())
        assert first_line["message"] == f"{process} started"

        running.send_signal(signal.SIGTERM)

        assert running.wait(timeout=5) == 0
    finally:
        running.kill()
