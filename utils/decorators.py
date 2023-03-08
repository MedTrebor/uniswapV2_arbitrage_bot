from functools import wraps
from threading import Lock

singleton_instances = {}
lock = Lock()


def singleton(cls):
    """Turn class into a singleton.
    Can be avoided with `new_singleton=True` flag when initiating object.
    Can be reinstantiated with `no_singleton=True` flag when initiating object.

    Example::
        >>> @singleton
        ... class Foo:
        ...     pass
        ...
        >>> f1, f2, f3 = Foo(), Foo(), Foo(no_singleton=True)
        >>> f4, f5 = Foo(new_singleton=True), Foo()
        >>> f1 is f2
        True
        >>> f1 is f3
        False
        >>> f1 is f4
        False
        >>> f4 is f5
        True
    """

    @wraps(cls)
    def inner(*args, no_singleton=False, new_singleton=False, **kwargs):
        with lock:
            global singleton_instances
            if no_singleton:
                return cls(*args, **kwargs)
            if new_singleton or cls not in singleton_instances:
                singleton_instances[cls] = cls(*args, **kwargs)
            return singleton_instances[cls]

    return inner


def remove_singleton(cls) -> None:
    """Remove class from singleton instances."""
    global singleton_instances
    del singleton_instances[cls]
