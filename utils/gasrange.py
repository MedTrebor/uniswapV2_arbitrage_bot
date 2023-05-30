from decimal import ROUND_UP, Decimal
from typing import Iterator


class GasPriceRange:
    """Iterate over gas prices increasing gas price by 10% on each iteration.
    If prices are floats, GWEI to WEI conversion will be applied.

    Example::
        >>> for price in GasPriceRange("1.000000001", int(3e9)):
        ...     print(price)
        ...
        1000000001
        1100000002
        1210000003
        1331000004
        1464100005
        1610510006
        1771561007
        1948717108
        2143588819
        2357947701
        2593742472
        3000000000
    """

    __slots__ = "start_price", "end_price"

    def __init__(
        self, start_price: Decimal | int | str, end_price: Decimal | int | str
    ) -> None:
        """Create gas price range interator. Last price will be ``end_price``.

        Args:
            start_price (Decimal | int | str): Starting gas price.
            end_price (Decimal | int | str): Ending gas price.

        Raises:
            TypeError: If prices are not valid type.
            ValueError: If ``start_price`` is greater than ``end_price`` or prices
                are not normal.
        """
        # typecheck
        if not isinstance(start_price, (Decimal, int, str)):
            raise TypeError(f"start_price can't be of type {type(start_price)}")
        if not isinstance(end_price, (Decimal, int, str)):
            raise TypeError(f"end_price can't be of type {type(end_price)}")

        # converting to WEI if price if float
        if isinstance(start_price, str) and "." in start_price:
            _start_price = (Decimal(start_price) * Decimal("1e9")).to_integral_value()
        else:
            _start_price = Decimal(start_price)

        if isinstance(end_price, str) and "." in end_price:
            _end_price = (Decimal(end_price) * Decimal("1e9")).to_integral_value()
        else:
            _end_price = Decimal(end_price)

        if _start_price.to_integral_value() != _start_price:
            self.start_price = (_start_price * Decimal("1e9")).to_integral_value()
        else:
            self.start_price = _start_price

        if _end_price.to_integral_value() != _end_price:
            self.end_price = (_end_price * Decimal("1e9")).to_integral_value()
        else:
            self.end_price = _end_price

        # checking if numbers are normal
        if not self.start_price.is_normal():
            raise ValueError(f"start_price ({start_price}) is not valid")
        if not self.end_price.is_normal():
            raise ValueError(f"end_price ({end_price}) is not valid")

        # checking if start price is lower than end price
        if self.start_price > self.end_price:
            raise ValueError(
                f"start_price ({start_price}) can't be greater than end_price ({end_price})"
            )

    def __iter__(self) -> Iterator[int]:
        curr_price = self.start_price
        if curr_price == self.end_price:
            yield curr_price

        while curr_price < self.end_price:
            next_price = (curr_price * Decimal("1.1")).to_integral_value(ROUND_UP)

            if next_price > self.end_price:
                curr_price = self.end_price

            yield int(curr_price)

            curr_price = next_price
