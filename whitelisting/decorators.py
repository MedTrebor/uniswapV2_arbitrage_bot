from functools import wraps
from typing import Callable, Concatenate, ParamSpec, TypeVar

from utils import WaitPrevious

P = ParamSpec("P")
R = TypeVar("R")


def cache_last_block(f: Callable[Concatenate[int, P], tuple[R, int]]) -> Callable[P, R]:
    cached_block = 0

    @wraps(f)
    def inner(*args: P.args, **kwargs: P.kwargs) -> R:
        nonlocal cached_block
        r, cached_block = f(cached_block, *args, **kwargs)
        return r

    return inner


def wait(waiter: WaitPrevious) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def outer(f: Callable[P, R]) -> Callable[P, R]:
        @wraps(f)
        def inner(*args: P.args, **kwargs: P.kwargs) -> R:
            waiter()
            return f(*args, **kwargs)

        return inner

    return outer
