from decimal import Decimal

from .config import CONFIG


lengths: dict[int, int] = {}  # type: ignore
min_gas_limits: list[Decimal | None] = [None] * 5  # type: ignore


for length, gas_limit in CONFIG["min_gas_limits"].items():
    length = int(length)

    lengths[length * 2 + 1] = gas_limit


for length, gas_limit in lengths.items():
    while len(min_gas_limits) < length:
        min_gas_limits.append(None)

    min_gas_limits.append(Decimal(gas_limit))


MIN_GAS_LIMITS: tuple[Decimal | None, ...] = tuple(min_gas_limits)
r"""Index of length of path is it's gas limit.

Example::
    >>> path = ["A", "AB", "B", "AB", "A"]
    >>> MIN_GAS_LIMITS
    (None, None, None, None, None, Decimal('170000'))
    >>> MIN_GAS_LIMITS[len(path)]
    Decimal('170000')
"""
