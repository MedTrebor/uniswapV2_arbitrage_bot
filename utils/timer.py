from datetime import timedelta
from functools import wraps
from threading import Lock, Thread, Timer
from time import perf_counter, sleep
from typing import Any, Callable, ParamSpec, Protocol, TypeVar

from .logger import Logger

log = Logger(__name__)


class TimePassed:
    """Used for checking if provided time has passed.

    Args:
        default (int | float, optional): Set default pass time. Defaults to 60.
    """

    __slots__ = "_lock", "_passed", "_default"

    def __init__(self, default: int | float = 60) -> None:
        self._lock = Lock()
        self._passed = True
        self._default = default

    def _trigger(self) -> None:
        with self._lock:
            self._passed = True

    def __call__(self, secs: int | float | None = None) -> bool:
        """Chek if previously provided time has passed.

        Args:
            secs (int | float | None, optional): How many ``secs`` have to pass.
                If not provided, will use ``_default`` property. Defaults to None.

        Returns:
            bool: ``True`` if there is provided time has passed, else ``False``.
        """
        with self._lock:
            if not self._passed:
                return False
            secs = secs or self._default
            self._passed = False
            t = Timer(secs, self._trigger)
            t.daemon = True
            t.start()
            return True


class WaitPrevious:
    """Used for waiting previously provided time.

    Blocks the code until previously provided time has passed.
    When previously provided time has passed continues the code and
    resets the timer.

    Args:
        secs (int | float, optional): Set default waiting time.
            Defaults to 60.
    """

    __slots__ = "_lock", "_default", "_started"

    def __init__(self, default: int | float = 60) -> None:
        self._lock = Lock()
        self._default = default
        self._started = False

    def _wait(self, secs: int | float) -> None:
        with self._lock:
            self._started = True
            sleep(secs)

    def __call__(self, secs: int | float | None = None) -> None:
        """Waits for previously provided seconds.

        Args:
            secs (int | float | None, optional): How long will next wait be.
                If not provided, will use ``_default`` property. Defaults to None.
        """
        secs = secs or self._default
        with self._lock:
            Thread(target=self._wait, daemon=True, args=[secs]).start()
        while not self._started:
            continue
        self._started = False


T = TypeVar("T")
P = ParamSpec("P")


def execution_time(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator to measure execution time of a function.

    Args:
        func (Callable[P, T]): Function.

    Returns:
        Callable[P, T]: Wrapped function.
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        start = perf_counter()
        result = func(*args, **kwargs)
        elpassed = perf_counter() - start

        log.debug(
            f"[magenta b]{func.__name__}[/] execution time: {timedelta(seconds=elpassed)}"
        )

        return result

    return wrapper


class MeasureTime(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> str:
        """Get formatted string with measured time.

        Args:
            args (Any): Will be formatted in previously provided string.
            kwargs (Any): Will be formatted in previously provided string.

        Returns:
            str: Formatted string.
        """
        ...


def measure_time(log_str: str) -> MeasureTime:
    """Meassure time until returned function is called and format provided log_str.
    Last field will be measured time if args are used.
    If keyword fields are used `t` represents measured time.

    Args:
        log_str (str): String to format.

    Examples::

        >>> format_log = measure_time("Func was executed {:,} times in {}.")
        >>> exe_num = random_func()
        >>> format_log(exe_num)
        Func was executed 3,135 times in 0:00:13.000440.

        >>> format_log = measure_time("Execution time: {t}. Count: {i:,.2f}.")
        >>> exe_num = random_func()
        >>> format_log(i=exe_num)
        Execution time: 0:00:09.013420. Count: 1,994.00.

    Returns:
        MeasureTime: Function to be called to format log.
    """
    start = perf_counter()

    def finish(*args: Any, **kwargs: Any) -> str:
        if kwargs:
            return log_str.format(**kwargs, t=timedelta(seconds=perf_counter() - start))
        return log_str.format(*args, timedelta(seconds=perf_counter() - start))

    return finish
