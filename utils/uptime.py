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

from threading import Lock, Thread
from time import sleep, time

import persistance


_lock: Lock = Lock()
_start_time = _current_time = time()
_prev_uptime = persistance.load_uptime()


def current() -> float:
    """Get uptime for current session.

    Returns:
        float: Uptime in seconds.
    """
    global _lock, _start_time

    with _lock:
        return time() - _start_time


def total() -> float:
    """Get total uptime for all seassions.

    Returns:
        float: Uptime in seconds.
    """
    global _lock, _current_time, _prev_uptime

    with _lock:
        return _prev_uptime + time() - _current_time


def _update() -> None:
    """Continuously update `uptime` in storage"""
    global _lock, _current_time, _prev_uptime

    while True:
        sleep(60)

        uptime = _prev_uptime + time() - _current_time
        persistance.save_uptime(uptime)

        with _lock:
            _prev_uptime = uptime
            _current_time = time()


# start continuously updating uptime in storage
Thread(target=_update, name="Uptime", daemon=True).start()
