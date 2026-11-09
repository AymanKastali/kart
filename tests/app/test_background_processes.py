import os
import signal
import subprocess
import sys

import pytest

from tests.app.test_settings import ENVIRONMENT


@pytest.mark.parametrize("process", ["worker", "scheduler"])
def test_a_background_process_stops_cleanly_on_sigterm(process: str) -> None:
    running = subprocess.Popen(  # noqa: S603 the command is fixed
        [sys.executable, "-m", f"kart.app.{process}"],
        stdout=subprocess.PIPE,
        env={**os.environ, **ENVIRONMENT},
        text=True,
    )
    try:
        assert running.stdout is not None
        assert running.stdout.readline().strip() == f"{process} started"

        running.send_signal(signal.SIGTERM)

        assert running.wait(timeout=5) == 0
    finally:
        running.kill()
