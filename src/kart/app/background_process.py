"""Shared start-up for the processes that have no HTTP server: `worker` and `scheduler`."""

import signal
import threading
from typing import TYPE_CHECKING

from kart.app.settings import Settings

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import FrameType


def _idle(_settings: Settings, stopped: threading.Event) -> None:
    stopped.wait()


def run_until_stopped(name: str, work: Callable[[Settings, threading.Event], None] = _idle) -> None:
    """Check the settings, announce the process, then `work` until SIGTERM (or Ctrl-C)."""
    settings = Settings()  # a missing variable stops the process here
    stopped = threading.Event()

    def stop(_signal: int, _frame: FrameType | None) -> None:
        stopped.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(f"{name} started", flush=True)  # noqa: T201 structured logging comes later
    work(settings, stopped)
