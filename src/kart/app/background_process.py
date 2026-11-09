"""Shared start-up for the processes that have no HTTP server: `worker` and `scheduler`."""

import signal
import threading
from typing import TYPE_CHECKING

from kart.app.settings import Settings

if TYPE_CHECKING:
    from types import FrameType


def run_until_stopped(name: str) -> None:
    """Check the settings, announce the process, then block until SIGTERM (or Ctrl-C)."""
    Settings()  # a missing variable stops the process here
    stopped = threading.Event()

    def stop(_signal: int, _frame: FrameType | None) -> None:
        stopped.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(f"{name} started", flush=True)  # noqa: T201 structured logging comes later
    stopped.wait()
