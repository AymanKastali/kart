"""Shared start-up for the processes that have no HTTP server: `worker` and `scheduler`."""

import signal
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import FrameType


def run_until_stopped(name: str) -> None:
    """Announce the process, then block until Docker stops it with SIGTERM (or Ctrl-C)."""
    stopped = threading.Event()

    def stop(_signal: int, _frame: FrameType | None) -> None:
        stopped.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(f"{name} started", flush=True)  # noqa: T201 structured logging comes later
    stopped.wait()
