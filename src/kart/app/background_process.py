"""Shared start-up for the processes that have no HTTP server: `worker` and `scheduler`."""

import logging
import signal
import threading
from typing import TYPE_CHECKING

from kart.app.observability import set_up_observability
from kart.app.settings import Settings

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import FrameType

_logger = logging.getLogger(__name__)


def _idle(_settings: Settings, stopped: threading.Event) -> None:
    stopped.wait()


def run_until_stopped(name: str, work: Callable[[Settings, threading.Event], None] = _idle) -> None:
    """Check the settings, announce the process, then `work` until SIGTERM (or Ctrl-C)."""
    settings = Settings()  # a missing variable stops the process here
    set_up_observability(name, settings)
    stopped = threading.Event()

    def stop(_signal: int, _frame: FrameType | None) -> None:
        stopped.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    _logger.info("%s started", name)
    work(settings, stopped)
