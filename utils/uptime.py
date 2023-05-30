"""Uptime of application.

Runs in seperate thread to update `uptime` in stoarage every minute.

Examples:
    Get uptime for current session::
        >>> uptime.current()
        123.456678

    Get total uptime for all sessions::
        >>> uptime.total()
        483903.44955
"""

from threading import Lock, Thread, Event
from time import sleep, perf_counter
from utils import Logger

import persistance

log = Logger(__name__)


_running_event: Event
_start_time: float
_prev_uptime: float

_lock: Lock = Lock()


def start() -> bool:
    """Start uptime measuring.

    Returns:
        bool: Success.
    """
    global _running_event, _lock, _start_time, _prev_uptime

    with _lock:
        try:
            if _running_event.is_set():
                return False
        except NameError:
            pass

        _prev_uptime = persistance.load_uptime()
        _start_time = perf_counter()

        _running_event = Event()
        _running_event.set()

        Thread(
            target=_update, name="Uptime", args=[_running_event], daemon=True
        ).start()

    return True


def stop() -> bool:
    """Stop uptime measuring.

    Returns:
        bool: Success.
    """
    global _running_event, _lock

    with _lock:
        try:
            if not _running_event.is_set():
                return False
        except NameError:
            return False

        _running_event.clear()

    return True


def current() -> float:
    """Get uptime for current session.

    Returns:
        float: Uptime in seconds.
    """
    global _lock, _start_time

    with _lock:
        return perf_counter() - _start_time


def total() -> float:
    """Get total uptime for all seassions.

    Returns:
        float: Uptime in seconds.
    """
    global _lock, _start_time, _prev_uptime

    with _lock:
        return _prev_uptime + perf_counter() - _start_time


def _update(running_event: Event) -> None:
    """Continuously update `uptime` in storage.

    Args:
        running_event (Event): Running event to controle function run.
    """
    global _lock, _start_time, _prev_uptime

    log.info("Uptime measurement started.")

    sleep(1)
    while running_event.is_set():
        with _lock:
            uptime = _prev_uptime + perf_counter() - _start_time
            persistance.save_uptime(uptime)

        sleep(1)

    log.info("Uptime measurement stopped.")
